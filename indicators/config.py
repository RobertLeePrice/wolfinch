#! /usr/bin/env python
'''
 Desc: 
 Global Market Indicators Configuration. 
 ref. implementation.
 All the globally available market Indicators are instantiated and configured here.
 If a market specific Indicators list is required, a similar config may be made specific to the market
 (c) Joshith Rayaroth Koderi
'''

from indicators.sma import SMA

market_indicators = []
init_done = False

def Configure ():
    global init_done, market_indicators
    #### Configure the Strategies below ######
    
    if init_done:
        return market_indicators
    
    # SMA15, SMA50
    sma15 = SMA ('sma15', 15)
    sma50 = SMA ('sma50', 50)
    
    # List of all the available strategies
    global market_indicators
    market_indicators = [
            sma15,
            sma50
        ]
    
    #### Configure the Strategies - end ######
    init_done = True
    return market_indicators

######### ******** MAIN ****** #########
if __name__ == '__main__':
    print ("Market Indicators Test")
    Configure ()
    
    
#EOF