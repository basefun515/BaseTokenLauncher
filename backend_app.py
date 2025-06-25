from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from web3 import Web3
import json


# --- Flask App Setup ---
app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# --- Configuration - Read from Environment Variables ---
RPC_URL = os.environ.get('RPC_URL')
PRIVATE_KEY = os.environ.get('PRIVATE_KEY', '').strip() # Use .get for safety and strip whitespace
# Read contract artifact path from environment variables
CONTRACT_ARTIFACT_PATH = os.environ.get('CONTRACT_ARTIFACT_PATH')
# Read fee recipient address from environment variables
FEE_RECIPIENT_ADDRESS = os.environ.get('FEE_RECIPIENT_ADDRESS')


# --- Web3 Connection (Initialize outside the route) ---
# Initialize Web3 only if RPC_URL is available
w3 = None
if RPC_URL:
    try:
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        # Check connection (optional, but good to know if the backend can connect)
        if not w3.is_connected():
            print(f"Warning: Backend could not connect to RPC URL: {RPC_URL}")
        else:
            print(f"Backend successfully connected to network: {RPC_URL}")
    except Exception as e:
        print(f"Error initializing Web3 with RPC_URL {RPC_URL}: {e}")
        w3 = None # Ensure w3 is None if initialization failed
else:
    print("Error: RPC_URL environment variable not set.")


# --- Deployment Function ---
def deploy_contract_backend(w3_instance, artifact_path, private_key, constructor_args):
    """Deploys a smart contract using web3.py for the backend."""
    if not private_key:
        return {"error": "Private key not configured in environment variables."}
    if not artifact_path:
        return {"error": "CONTRACT_ARTIFACT_PATH environment variable not set."}
    if not w3_instance or not w3_instance.is_connected():
        return {"error": f"Backend not connected to network. RPC_URL: {RPC_URL}"}


    # Re-check artifact file existence here as well before trying to open
    if not os.path.exists(artifact_path):
         return {"error": f"Contract artifact file not found at {artifact_path}. Ensure contract is compiled and path is correct."}


    try:
        w3 = w3_instance

        # Ensure private key is bytes or hex string
        account = w3.eth.account.from_key(private_key)
        print(f"Backend deploying from account: {account.address}")

        try:
            with open(artifact_path, 'r') as f:
                contract_json = json.load(f)
                abi = contract_json['abi']
                bytecode = contract_json['bytecode']
        except FileNotFoundError:
            # This check is redundant if done before, but kept for safety
            return {"error": f"Contract artifact file not found at {artifact_path}. Ensure contract is compiled."}
        except json.JSONDecodeError:
             return {"error": f"Could not decode JSON from {artifact_path}. Ensure it's a valid JSON file."}


        Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
        nonce = w3.eth.get_transaction_count(account.address)

        print("Backend estimating gas...")
        try:
            gas_estimate = Contract.constructor(*constructor_args).estimate_gas({
                'from': account.address,
                'nonce': nonce
            })
            print(f"Backend gas estimate: {gas_estimate}")
        except Exception as e:
            print(f"Backend gas estimation error: {e}")
            # Attempt to get estimated gas price to provide more context if gas estimation fails
            try:
                estimated_gas_price = w3.eth.gas_price
                print(f"Current estimated gas price: {w3.from_wei(estimated_gas_price, 'gwei')} gwei")
            except Exception as gas_price_e:
                print(f"Could not retrieve current gas price in gas estimation error handler: {gas_price_e}")
            return {"error": f"Error estimating gas: {e}. Check testnet ETH balance and constructor args."}

        try:
            current_gas_price = w3.eth.gas_price
            gas_price_to_use = current_gas_price
        except Exception as e:
            print(f"Backend error fetching gas price, using fallback: {e}")
            gas_price_to_use = w3.to_wei('1', 'gwei') # Fallback fixed gas price


        transaction = Contract.constructor(*constructor_args).build_transaction({
            'from': account.address,
            'nonce': nonce,
            'gas': gas_estimate + 100000, # Add a buffer
            'gasPrice': gas_price_to_use,
            'chainId': w3.eth.chain_id,
        })
        print("Backend transaction built.")

        signed_transaction = w3.eth.account.sign_transaction(transaction, private_key)
        print("Backend transaction signed.")

        print("Backend sending transaction...")
        tx_hash = w3.eth.send_raw_transaction(signed_transaction.rawTransaction)
        print(f"Backend transaction sent. Hash: {w3.to_hex(tx_hash)}")

        print("Backend waiting for transaction to be mined...")
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if tx_receipt.status == 1:
            contract_address = tx_receipt.contractAddress
            print(f"Backend contract deployed at address: {contract_address}")
            return {"contractAddress": contract_address}
        else:
            print("Backend transaction failed!")
            print("Backend Receipt:", tx_receipt)
            # Attempt to get transaction error details if available
            try:
                 tx = w3.eth.get_transaction(tx_hash)
                 print("Transaction receipt status is 0, indicating failure.")
            except Exception as tx_error:
                 print(f"Could not retrieve transaction details for troubleshooting: {tx_error}")

            return {"error": "Transaction failed during deployment. Check testnet explorer."}

    except Exception as e:
        print(f"An unexpected backend error occurred during deployment: {e}")
        return {"error": f"An unexpected error occurred: {e}"}


# --- Flask Route for Deployment ---
@app.route('/deploy-token', methods=['POST'])
def deploy_token():
    """Receives token details and triggers contract deployment."""
    print("Received request to /deploy-token")
    data = request.get_json()

    if not data:
        print("No JSON data received.")
        return jsonify({"error": "Invalid JSON"}), 400

    token_name = data.get('name')
    token_symbol = data.get('symbol')

    if not token_name or not token_symbol:
        print("Missing token name or symbol in request.")
        return jsonify({"error": "Missing token name or symbol"}), 400

    if not FEE_RECIPIENT_ADDRESS:
         print("Error: FEE_RECIPIENT_ADDRESS environment variable not set.")
         return jsonify({"error": "Backend configuration error: Fee recipient address not set."}), 500

    print(f"Deploying token: {token_name} ({token_symbol})")

    # --- Hardcoded Parameters for Pump.fun model ---
    # LP Migration Market Cap (example: 0.01 ETH equivalent)
    # Using w3.to_wei here as w3 is initialized outside the function
    if w3 and w3.is_connected():
        lp_migration_market_cap_wei = w3.to_wei(0.01, 'ether')
    else:
         # Fallback value if w3 is not connected, though deployment will likely fail anyway
         print("Warning: w3 not connected in backend route, using fallback LP market cap.")
         lp_migration_market_cap_wei = 10**16 # Defaulting to 0.01 ether in wei


    constructor_arguments = [
        token_name,
        token_symbol,
        lp_migration_market_cap_wei,
        FEE_RECIPIENT_ADDRESS # Use the address from environment variable
    ]

    # Call the deployment function
    deployment_result = deploy_contract_backend(
        w3, # Pass the web3 instance
        CONTRACT_ARTIFACT_PATH,
        PRIVATE_KEY,
        constructor_arguments
    )

    if "contractAddress" in deployment_result:
        return jsonify({"tokenAddress": deployment_result["contractAddress"]}), 200
    else:
        # Return a more specific error if available
        return jsonify({"error": deployment_result.get("error", "Deployment failed")}), 500


# --- Running the Flask App ---
# This is for local testing purposes only (like in Colab directly).
# Render will use the Procfile and Waitress.
if __name__ == '__main__':
    print("Starting Flask backend server locally (for testing)...")
    # This part will not run on Render because Render uses the Procfile
    # You can keep this for local debugging if needed.
    # Make sure to set environment variables manually for local testing.
    app.run(host='0.0.0.0', port=5000, debug=True)
