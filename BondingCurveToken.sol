// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/math/SafeMath.sol";
import "hardhat/console.sol";


contract BondingCurveToken is ERC20, Ownable {
    using SafeMath for uint256;

    // Bonding curve parameters (simplified example)
    uint256 public constant INITIAL_PRICE = 1 ether; // 1 token = 1 ether (example)
    uint256 public constant PRICE_INCREASE_RATE = 10**15; // Price increases by 0.001 ether per token sold
    uint256 public constant MAX_SUPPLY = 1000000 ether; // Maximum total supply

    // Fee parameters
    uint256 public constant BUY_FEE_BPS = 50; // 0.5% buy fee
    uint256 public constant SELL_FEE_BPS = 100; // 1% sell fee
    address public feeRecipient;

    // LP Migration parameters
    uint256 public lpMigrationMarketCap;
    bool public lpMigrated = false;
    address public constant DEX_ROUTER = 0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D; // Uniswap V2 Router (example)

    event TokensPurchased(address indexed buyer, uint256 etherAmount, uint256 tokenAmount);
    event TokensSold(address indexed seller, uint256 tokenAmount, uint256 etherAmount);
    event LPMigrated(uint256 marketCap);

    constructor(
        string memory name,
        string memory symbol,
        uint256 _lpMigrationMarketCap,
        address _feeRecipient
    ) ERC20(name, symbol) Ownable(msg.sender) {
        lpMigrationMarketCap = _lpMigrationMarketCap;
        feeRecipient = _feeRecipient;
    }

    // Function to get the current price based on tokens sold
    function getCurrentPrice() public view returns (uint256) {
        uint256 tokensSold = MAX_SUPPLY.sub(totalSupply());
        return INITIAL_PRICE.add(tokensSold.mul(PRICE_INCREASE_RATE));
    }

    // Buy tokens from the bonding curve
    function buyTokens() public payable {
        require(!lpMigrated, "LP has already been migrated.");

        uint256 currentPrice = getCurrentPrice();
        uint256 tokenAmount = msg.value.mul(1 ether).div(currentPrice); // Simplified calculation
        require(totalSupply().add(tokenAmount) <= MAX_SUPPLY, "Exceeds max supply");

        // Calculate fee
        uint256 feeAmount = msg.value.mul(BUY_FEE_BPS).div(10000);
        uint256 amountAfterFee = msg.value.sub(feeAmount);

        // Mint tokens to the buyer
        _mint(msg.sender, tokenAmount);

        // Send fee to recipient
        payable(feeRecipient).transfer(feeAmount);

        emit TokensPurchased(msg.sender, msg.value, tokenAmount);

        // Check for LP migration trigger
        checkLPMigration();
    }

    // Sell tokens back to the bonding curve
    function sellTokens(uint256 tokenAmount) public {
        require(!lpMigrated, "LP has already been migrated.");
        require(balanceOf(msg.sender) >= tokenAmount, "Insufficient token balance");

        uint256 currentPrice = getCurrentPrice();
        uint256 etherAmount = tokenAmount.mul(currentPrice).div(1 ether); // Simplified calculation

        // Calculate fee
        uint256 feeAmount = etherAmount.mul(SELL_FEE_BPS).div(10000);
        uint256 amountAfterFee = etherAmount.sub(feeAmount);

        // Burn tokens
        _burn(msg.sender, tokenAmount);

        // Send ether to the seller
        payable(msg.sender).transfer(amountAfterFee);

        // Send fee to recipient
        payable(feeRecipient).transfer(feeAmount);

        emit TokensSold(msg.sender, tokenAmount, etherAmount);

        // Check for LP migration trigger
        checkLPMigration();
    }

    // Check if LP migration market cap is reached and trigger migration
    function checkLPMigration() internal {
        if (!lpMigrated) {
            uint256 currentMarketCap = totalSupply().mul(getCurrentPrice()).div(1 ether);
            if (currentMarketCap >= lpMigrationMarketCap) {
                migrateLP();
                lpMigrated = true;
                emit LPMigrated(currentMarketCap);
            }
        }
    }

    // Function to migrate LP (simplified simulation)
    function migrateLP() internal onlyOwner {
        // In a real scenario, this would involve:
        // 1. Approving the DEX router to spend tokens and ether.
        // 2. Calling the addLiquidity or addLiquidityETH function on the DEX router.
        // 3. Sending remaining ether (if any) to the fee recipient or a designated address.

        // For this simulation, we'll just print a message.
        console.log("LP Migration triggered!");
        // A real implementation would transfer collected ether and remaining tokens to the DEX
        // and lock the LP tokens.
    }

    // Function to receive ether
    receive() external payable {
        buyTokens();
    }
}
