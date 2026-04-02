# Stabilisation Mechanism

## Anthill Protocol

* _**ANT trades below the $1 target price**_

When the ANTT price is below its target price of $1, token holders can purchase ANT Bonds (ANTB) by burning ANTT to reduce the circulating supply with a 1:1 ratio, and Bonds will be burnt when users redeem ANTT with a premium bonus.

In case of redemption, an amount of ANTT will be minted according to the TWAP at the beginning of the epoch (for example, if the ANTT price is $1.1 then one Bond burnt will get back 1.1 ANTT). It is important to note that Bonds have no expiry after purchase.

* _**ANTT trades above the $1 target price**_

When the ANTT price is above its 1$ peg, the token supply will have to expand to push it back down to 1$ and the contract will allow the redemption of the ANTB.

When the price of ANTT continues trading above the $1 target price after bond redemption, the contract mints an appropriate amount of new ANTT. This will be distributed to the Boardroom Stakers.

This three token system creates incentives through seigniorage, always pushing ANTT towards its peg. ANTS is used to redistribute the seigniorage from inflating the asset, while ANTB is used to establish a price floor while ANTT is in its deflationary state.

* _**Epoch Expansion**_

Capped at +50% of the current expansion cap if there are bonds to be redeemed and follows the expansion cap if the treasury is sufficiently full to meet bond redemption (See table below for detailed information)

Total ANT Supply Expansion / Bonds Issued per Epoch

* Under 500k 4.00% Cap
* 500k+ 3.50% Cap
* 1m+ 3.00% Cap
* 2m+ 2.50% Cap
* 5m+ 2.00% Cap
* 10m+ 1.50% Cap
* 20m+ 1.25% Cap
* 50m+ 1.00% Cap
* 100m+ 0.75% Cap
* 200m+ 0.50% Cap
* 1B+ 0.25% Cap

**Bootstrap period:** 1st week (21 epochs) goes with full expansion 4% each epoch

## Unique Algorithm <a href="#unique-algorithm" id="unique-algorithm"></a>

* (Boardroom) Epoch duration: 8 hours during expansion and 6 hours during contraction — the protocol reacts faster to stabilise ANTT price to peg as compared to other protocols with longer epoch durations
* Epoch Expansion: Capped at 6% if there are bonds to be redeemed, 4% if the treasury is sufficiently full to meet bond redemption
* ANTB tokens do not expire and this greatly reduces the risk for bond buyers
* Price feed oracle for TWAP is based on the average of 2 liquidity pool pairs (i.e. ANTT/USD and ANTT/MATIC) which makes it more difficult to manipulate
* No discount for bond purchase, but a premium bonus for bond redemptions if users were to wait for ANTT to increase even more than the target price.
* Riding on [anthill.community](https://anthill.community/) various resources and ecosystem pillars, ANTT will find its ever-growing utilities right after launch, which is its great advantage over other algorithmic stablecoins.
