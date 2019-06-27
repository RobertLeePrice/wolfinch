# '''
#  OldMonk Auto trading Bot
#  Desc:  exchange interactions Simulation
#  (c) Joshith
# '''

# import requests
# import json
import uuid
import time
from datetime import datetime
# from dateutil.tz import tzlocal
from decimal import Decimal
import copy

from utils import getLogger
from market import feed_deQ, feed_Q_process_msg, get_market_list, flush_all_stats
import exchange_sim
#from market.order import Order, TradeRequest
#from market import feed_enQ

__name__ = "SIM-OPS"
log = getLogger (__name__)
log.setLevel (log.CRITICAL)

###### SIMULATOR Global switch ######
backtesting_on = False
import_only = False

####### Private #########
def set_initial_acc_values (market):
    #Setup the initial params
    market.fund.set_initial_value(Decimal(2000))
#     market.fund.set_hold_value(Decimal(100))
    market.fund.set_fund_liquidity_percent(90)       #### Limit the fund to 90%
    market.fund.set_max_per_buy_fund_value(90)
    market.asset.set_initial_size(Decimal(1))
    market.asset.set_hold_size( Decimal(0.1))
    market.asset.set_max_per_trade_size(Decimal(0.01))
        
def finish_backtesting(market):
    log.info ("finish backtesting. market:%s"%(market.name))

    # sell acquired assets and come back to initial state
    market.close_all_positions()
    return True
    
def do_backtesting ():
    # don't sleep for backtesting    
    sleep_time = 0
    done = False
    all_done = 0
        
    for market in get_market_list():
        log.info ("backtest setup for market: %s num_candles:%d"%(market.name, market.num_candles))
        market.backtesting_idx = 0
        set_initial_acc_values(market)        
                          
    while (all_done < 5) : 
        # check for the msg in the feed Q and process, with timeout
        done = True
        msg = feed_deQ(sleep_time)
        while (msg != None):
            feed_Q_process_msg (msg)
            msg = feed_deQ(0)        
        for market in get_market_list():
            market.update_market_states()
            # Trade only on primary markets
            if (market.primary == True and (market.backtesting_idx < market.num_candles)):
#                 log.info ("BACKTEST(%d): processing on market: exchange (%s) product: %s"%(
#                     market.backtesting_idx, market.exchange_name, market.name))     
                signal = market.generate_trade_signal (market.backtesting_idx)
                market.consume_trade_signal (signal)
                if (exchange_sim.simulator_on):
                    exchange_sim.market_simulator_run (market)
                #if atleast one market is not done, we will continue
                done = False
                market.backtesting_idx += 1
            elif done == True:
                finish_backtesting(market)
                market.backtesting_idx = market.num_candles - 1
                if (exchange_sim.simulator_on):
                    exchange_sim.market_simulator_run (market)                
                #let's do few iterations and make sure everything is really done!
                all_done += 1 
                       
    #end While(true)
def show_stats ():
    flush_all_stats()

############# Public APIs ######################
        
def market_backtesting_run ():
    """
    market backtesting 
    """
    log.debug("starting backtesting")    
    do_backtesting()
    log.info ("backtesting complete. ")
    show_stats ()

genetic_optimizer_on = False
gaDecisionConfig = {}
def market_backtesting_ga_hook ():
    """
    market backtesting hook for ga
    """
    global backtesting_on
    
    exchange_sim.simulator_on = True
    backtesting_on = True
    
    log.debug("starting backtesting")    
    do_backtesting()
    log.info ("backtesting complete. ")
    show_stats ()
    

#EOF
