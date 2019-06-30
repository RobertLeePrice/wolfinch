# '''
#  OldMonk Auto trading Bot
#  Desc:  exchange interactions Simulation
#  (c) Joshith
# '''
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import uuid
import sys
# import json
from bintrees import RBTree
from decimal import Decimal

from utils import getLogger
import stats

log = getLogger('ORDER-BOOK')
log.setLevel(log.CRITICAL)

class Position ():
    
    buy     = None
    sell    = None
    profit = Decimal(0)
    stop_loss = Decimal(0)
    take_profit = Decimal(0)
    open_time = None
    closed_time = None
    status = ''  #'open'|closed|close_pending
    def __init__(self, buy=None, sell=None):
        self.add_buy(buy)
        self.add_sell(sell)
        
    def add_buy(self, order):
        if order == None:
            return
        self.buy = order
        self.update_state("open")
        self.open_time = order.create_time
    
    def add_sell(self, order):
        if order == None:
            return
        self.sell = order
        self.closed_time = order.create_time
    
    def update_state (self, status):
        if status == "open" or status == "close_pending" or status == "closed":
            self.status = status
            if status == "closed":
                self.profit = Decimal((self.sell.get_price() - self.buy.get_price())*self.sell.get_asset())
        else:
            log.critical ("Unknown position status(%s)"%(status))
            raise Exception ("Unknown position status(%s)"%(status))
    def get_profit(self):
        return self.profit
    def update_stop_loss(self, market_rate, sl_rate):
        new_sl = Decimal(round(market_rate*(1 - sl_rate*Decimal(.01)), 8))
        if new_sl > self.stop_loss:
            self.stop_loss = new_sl
#             log.debug("Updated stop_loss (%f) for position. rate:%d"%(self.stop_loss, sl_rate))
            return True
        else:
            return False
    def set_stop_loss(self, market_rate, sl_rate):
        self.stop_loss = Decimal(round(market_rate*(1 - sl_rate*Decimal(.01)), 8))
        log.debug("setting stop_loss (%f) for position. rate:%d"%(self.stop_loss, sl_rate))                
    def get_stop_loss(self):
        return self.stop_loss      
    def set_take_profit(self, market_rate, tp_rate):
        self.take_profit = Decimal(round(market_rate*(1 + tp_rate*Decimal(.01)), 8))
        log.debug("setting take_profit(%f) for position. rate:%d"%(self.take_profit, tp_rate))                        
    def get_take_profit(self):
        return self.take_profit        
    def __str__(self):
        buy_str = str(self.buy) if self.buy else "null"
        sell_str = str(self.buy) if self.sell else "null"        
        return """{\n"status": "%s", "open_time":"%s", "closed_time":"%s", "profit": %f, "stop_loss": %f, "take_profit":%f,
"buy":%s\n,"sell":%s\n}"""%(self.status, self.open_time, self.closed_time, self.profit, self.stop_loss, self.take_profit,
                            buy_str, sell_str)
    def __repr__(self):
        return self.__str__()
        

class OrderBook():

    def __init__(self, market=None, bids=None, asks=None, log_to=None):
        self._asks = RBTree()
        self._bids = RBTree()
        self.book_valid = False
        self.new_book (bids, asks)
        self._sequence = -1
        self.market = market        
        self._log_to = log_to
        if self._log_to:
            assert hasattr(self._log_to, 'write')
        # My order Details    
        self.total_order_count = 0
        self.total_open_order_count = 0        
        self.pending_buy_orders_db = {}
        self.pending_sell_orders_db = {}
        self.traded_buy_orders_db = []
        self.traded_sell_orders_db = []
        
        # positions
        self.all_positions = []
        self.open_positions = []
        self.close_pending_positions = {}
        self.closed_positions = []
        
        #trade Reqs
        self.pending_trade_req = []  # TODO: FIXME: jork: this better be a nice AVL tree of sort
    def __str__(self):
        return """
{"position_all": %d, "open": %d, "close_pending": %d, "closed": %d}"""%(len(self.all_positions), len(self.open_positions),
                                len(self.close_pending_positions), len(self.closed_positions))
                    
    def add_pending_trade_req(self, trade_req):
        self.pending_trade_req.append(trade_req)
    def remove_pending_trade_req(self, trade_req):
        # primitive 
        self.pending_trade_req.remove(trade_req)
        
    def open_position (self, buy_order):
        #open positions with buy orders only (we don't support 'short' now)
#         log.debug ("open_position order: %s"%(buy_order))
        position = Position(buy=buy_order)
        if self.market.tradeConfig["stop_loss_enabled"]:
            position.set_stop_loss(buy_order.get_price(), self.market.tradeConfig["stop_loss_rate"])
        if self.market.tradeConfig["take_profit_enabled"]:
            position.set_take_profit(buy_order.get_price(), self.market.tradeConfig["take_profit_rate"])
                
        self.all_positions.append(position)
        self.open_positions.append(position)        
#         log.debug ("\n\n\n***open_position: open(%d) closed(%d) close_pend(%d)"%(len(self.open_positions), len(self.closed_positions), len(self.close_pending_positions)))  
          
    def get_closable_position(self):
        log.debug ("get_closable_position ")    
            
        #get last open position for now
        # TODO: FIXME: This may not be the best way. might cause race with below api with multi thread/multi exch
        pos = None
        if len(self.open_positions):
            pos = self.open_positions.pop()
            if (self.close_pending_positions.get(uuid.UUID(pos.buy.id))):
                log.critical("Position already close pending \npos:%s"%pos)
                raise ("Duplicate close pending position")            
            self.close_pending_positions[uuid.UUID(pos.buy.id)] = pos
#         log.debug ("\n\n\n***get_closable_position: open(%d) closed(%d) close_pend(%d) \n pos: %s"%(
#             len(self.open_positions), len(self.closed_positions), len(self.close_pending_positions), pos))
        return pos
        
    def close_position_pending(self, sell_order):
        # TODO: FIXME: This may not be the best way. might cause race with below api with multi thread/multi exch
        log.debug ("close_position_pending order:%s"%(sell_order.id))
#         log.debug ("\n\n\n***close_position_pending: open(%d) closed(%d) close_pend(%d)\n"%(
#             len(self.open_positions), len(self.closed_positions), len(self.close_pending_positions)))  
        pos = self.close_pending_positions.get(uuid.UUID(sell_order.id))
        if pos:
            log.debug ("close_position_pending: sell order(%s) already in pending_list. do nothing"%(sell_order.id))
            return pos
        #find a close_pending pos without sell attached.
#         for k, pos in self.close_pending_positions.iteritems():
        k = sell_order.buy_id
        if not k:
            log.critical("Invalid buy_id attached to order:%s"%(sell_order.id))
            raise Exception("Invalid buy_id attached to order")            
        pos = self.close_pending_positions.get(k)
        if pos:
            #find the pos without sell attached. and reinsert after attach
#             log.debug ("pos:\n%s"%(pos))
            if pos.sell == None:
                pos.add_sell(sell_order)
                pos.update_state("closed")                
                del(self.close_pending_positions[k])
                self.close_pending_positions[uuid.UUID(sell_order.id)] = pos
#                 log.debug ("\n\n\n***close_position_pending: open(%d) closed(%d) close_pend(%d)"%(len(self.open_positions), len(self.closed_positions), len(self.close_pending_positions)))                  
                return pos
            else:
                log.critical("Wrong sell attached to pos:%s"%(pos))
                raise Exception("Wrong sell attached to pos")
        else:
            #something is very wrong
            log.critical("Unable to find pending position for close id: %s"%(sell_order.id))
            raise Exception ("Unable to find pending position for close")
    def close_position_failed(self, sell_order):
        log.debug ("close_position_failed order: %s"%(sell_order.id))
#         log.debug ("\n\n\n***close_position_failed: open(%d) closed(%d) close_pend(%d)"%(len(self.open_positions), len(self.closed_positions), len(self.close_pending_positions)))  
           
        id = uuid.UUID(sell_order.id)
        position = self.close_pending_positions.get(id)
        if position:
            position.sell = None
            self.close_pending_positions.pop(id, None)
            self.open_positions.append(position)
        else:
            log.critical ("Unable to get close_pending position. order_id: %s"%(sell_order.id)) 
    def close_position (self, sell_order):
        log.debug ("close_position order: %s"%(sell_order.id))
        id = uuid.UUID(sell_order.id)
        position = self.close_pending_positions.pop(id, None)
        if position:
            position.add_sell (sell_order)
            position.update_state("closed")
            profit = position.get_profit()
            self.market.fund.current_realized_profit += profit
            if profit > 0 :
                self.market.num_success_trade += 1
            else:
                self.market.num_failed_trade += 1
            self.closed_positions.append(position)
        else:
            log.critical ("Unable to get close_pending position. order_id: %s"%(sell_order.id))
#         log.debug ("\n\n\n***close_position: open(%d) closed(%d) close_pend(%d)\n pos:%s"%(
#             len(self.open_positions), len(self.closed_positions), len(self.close_pending_positions), position))              
        
    def smart_stop_loss_update_positions(self, market_rate, sl_rate):
#         return sl_pos_list
        for pos in self.open_positions:
            pos.update_stop_loss(market_rate, sl_rate)
#             if pos.update_stop_loss(market_rate, sl_rate):
#                 log.critical ("smart updated stop_loss(%f) for position market_rate(%f)"%(pos.get_stop_loss(), market_rate))
    def get_stop_loss_positions(self, market_rate):
        sl_pos_list = []
#         return sl_pos_list
        for pos in self.open_positions[:]:
            if pos.get_stop_loss() >= market_rate:
                log.debug ("Found a position hit stop_loss(%f) market_rate(%f)"%(pos.get_stop_loss(),market_rate))
                self.market.num_stop_loss_hit += 1
                sl_pos_list.append(pos)
                self.open_positions.remove(pos)
                if (self.close_pending_positions.get(uuid.UUID(pos.buy.id))):
                    log.critical("Position already close pending \npos:%s"%pos)
                    raise ("Duplicate close pending position")            
                self.close_pending_positions[uuid.UUID(pos.buy.id)] = pos
        return sl_pos_list
    def get_take_profit_positions(self, market_rate):
        tp_pos_list = []
        for pos in self.open_positions[:]:
            if pos.get_take_profit() <= market_rate:
                log.info ("Found a position hit take_profit")
                self.market.num_take_profit_hit += 1
                tp_pos_list.append(pos)
                self.open_positions.remove(pos)
                if (self.close_pending_positions.get(uuid.UUID(pos.buy.id))):
                    log.critical("Position already close pending \npos:%s"%pos)
                    raise ("Duplicate close pending position")            
                self.close_pending_positions[uuid.UUID(pos.buy.id)] = pos
        return tp_pos_list
            
    def add_or_update_pending_buy_order(self, order):
        id = uuid.UUID(order.id)
        if not self.pending_buy_orders_db.get(id):
            self.total_open_order_count += 1
            self.total_order_count += 1 
        self.pending_buy_orders_db[id] = order
    def get_pending_buy_order(self, order_id):
        return self.pending_buy_orders_db.get (order_id)
    def add_traded_buy_order(self, order):
        self.total_open_order_count -= 1
        del (self.pending_buy_orders_db[uuid.UUID(order.id)])
        self.traded_buy_orders_db.append(order)
        #if this is a successful order, we have a new position open
        if order.status_reason == "filled":
            self.open_position(order)

    def add_or_update_pending_sell_order(self, order):
        id = uuid.UUID(order.id)
        if not self.pending_sell_orders_db.get(id):
            self.total_open_order_count += 1
            self.total_order_count += 1        
        self.pending_sell_orders_db[id] = order
            
    def get_pending_sell_order(self, order_id):
        self.pending_sell_orders_db.get (order_id)
    def add_traded_sell_order(self, order):
        del (self.pending_sell_orders_db[uuid.UUID(order.id)])
        self.total_open_order_count -= 1
        self.traded_sell_orders_db.append(order)
        #close/reopen position
        #TODO: TBD: more checks required??
        if order.status_reason == "filled":
            log.debug("closed position order: %s"%(order.id))
            self.close_position(order)
        else:
            log.critical("closed position failed order: %s"%(order))            
            self.close_position_failed(order)
        
    def add_order_list (self, bids, asks):
        if (asks):
            self.add_asks (asks)
        if (bids):            
            self.add_bids (bids)
                
    def dump_traded_orders (self, fd=sys.stdout):
        traded = str(self.traded_buy_orders_db + self.traded_sell_orders_db)
        fd.write(traded)
    def dump_positions (self, fd=sys.stdout):
        fd.write (str(self.all_positions))
#         
#     def on_sequence_gap(self, gap_start, gap_end):
#         self.reset_book()
#         print('Error: messages missing ({} - {}). Re-initializing  book at sequence.'.format(
#             gap_start, gap_end, self._sequence))

####### Public API #######
        
    def add_or_update_my_order (self, order):
        '''
        Handle a new order update msg
        return : order
        '''
        if (not order):
            return None
        order_id = uuid.UUID(order.id)
        order_status = order.status_type
        order_side = order.side
        if (not order_id):
            log.critical ("Invalid order_id: status:%s side: %s" % (order_status, order_side))
            return None
        current_order = None
        if (order_side == 'buy'):
            current_order = self.get_pending_buy_order(order_id)
        else:
            current_order = self.get_pending_sell_order(order_id)
            
        if current_order != None:
            # Copy whatever available, new gets precedence
            # money, asset
            order.request_size = order.request_size or current_order.request_size
            order.price = order.price or current_order.price
            order.funds = order.funds or current_order.funds
            order.fees = order.fees or current_order.fees
            if order_status != 'done':
                order.remaining_size = order.remaining_size or current_order.remaining_size
            # other data
            order.create_time = order.create_time or current_order.create_time
            order.update_time = order.update_time or current_order.update_time
            order.order_type = order.order_type or current_order.order_type
            order.product_id = order.product_id or current_order.product_id
        else:
            # this is a new order for us (not necessary placed by us, hence need this logic here)
            log.debug ("New Order Entry To be Inserted: total_order_count: %d "
                       "total_open_order_count: %d " % (self.total_order_count, self.total_open_order_count))
            
        if (order_side == 'buy'):
            # insert/replace the order
            self.add_or_update_pending_buy_order(order) 
            if (order_status == 'done'):
                # a previously placed order is completed, remove from open order, add to completed orderlist
                self.add_traded_buy_order(order)
                log.debug ("Buy order Done: total_order_count: %d "
                       "total_open_order_count: %d "
                       "traded_buy_orders_count: %d" % (self.total_order_count,
                                                       self.total_open_order_count,
                                                       len(self.traded_buy_orders_db)))
            elif (order_status in ['pending', 'open', 'received', 'match']):
                # Nothing much to do for us here
                log.info ("Buy order_id(%s) Status: %s" % (str(order_id), order_status))       
            else:
                log.critical("UNKNOWN buy order status: %s" % (order_status))
                raise Exception("UNKNOWN buy order status: %s" % (order_status))
                return None
        elif (order_side == 'sell'):
            # insert/replace the order
            self.add_or_update_pending_sell_order(order) 
            if (order_status == 'done'):
                # a previously placed order is completed, remove from open order, add to completed orderlist      
                self.add_traded_sell_order(order)
                log.debug ("Sell order Done: total_order_count: %d "
                       "total_open_order_count: %d "
                       "traded_sell_orders_count: %d" % (self.total_order_count,
                                                       self.total_open_order_count,
                                                       len(self.traded_sell_orders_db)))    
            elif (order_status in ['pending', 'open', 'received', 'match']):
                # Nothing much to do for us here
                log.info ("Sell order_id(%s) Status: %s" % (str(order_id), order_status))
                self.close_position_pending(order)
            else:
                log.critical("UNKNOWN sell order status: %s" % (order_status))
                raise Exception("UNKNOWN buy order status: %s" % (order_status))                
                return None
        else:
            log.critical("Invalid order :%s" % (order))
            raise Exception("Invalid order :%s" % (order))            
            return None
#         log.debug ("Order: %s\n"%(str(order)))
        stats.stats_update (self.market, order)
        return order
    
    ######### L2 Order book for Exchange, product ########
    def new_book (self, bids, asks):
        log.info ("Building new order book")
        if (bids and len(bids)) or (asks and len(asks)):
            self.add_order_list(bids, asks)            
            self.book_valid = True
        else :
            self.book_valid = False 

    def reset_book(self):
        self._asks = RBTree()
        self._bids = RBTree()
        res = self.market.exchange.get_product_order_book(self.market.product_id, level=3)
        # log.debug ("%s"%(str(res)))     
        if res == None:
            log.error ("Unable to get orderbook for exchange(%s) product: %s"%(self.market.exchange.name, self.market.product_id))
            return
        for bid in res['bids']:
            new_size = Decimal(bid[1]) 
            price = Decimal(bid[0])
            new_size += Decimal((self.get_bids(price) or 0))
            self.set_bids(price, new_size)
        for ask in res['asks']:
            new_size = Decimal(ask[1]) 
            price = Decimal(ask[0])
            new_size += Decimal((self.get_asks(price) or 0))
            self.set_asks(price, new_size)
        self._sequence = Decimal(res['sequence'])
        self.book_valid = True
#         print ("asks: %s"%(str(self._asks)))
#         print ("bids: %s"%(str(self._bids)))
                
    def add_asks (self, asks):
        ''' 
        asks = [ [price, size]]
        '''
        for ask in asks:
            price = Decimal(ask[0])
            size = Decimal(ask[1])
            if size > 0:  # size > 0 add, size = 0 remove
                self.set_asks(price, size)
            else:
                if (self.get_asks(price)):
                    self.remove_asks(price)                      
            
    def get_ask(self):
        return self._asks.min_key()

    def get_asks(self, price):
        return self._asks.get(price)

    def remove_asks(self, price):
        self._asks.remove(price)

    def set_asks(self, price, asks):
        price = round(price, 8)
        asks = round (asks, 8)
        log.debug ("set_asks: price: %g size: %g" % (price, asks))        
        self._asks.insert(price, asks)

    def add_bids (self, bids):
        ''' 
        bids = [ [price, size]]
        '''
        for bid in bids:
            price = Decimal(bid[0])
            size = Decimal(bid[1])
            if size > 0:  # size > 0 add, size = 0 remove
                self.set_bids(price, size)
            else:
                if (self.get_bids(price)):
                    self.remove_bids(price)      
            
    def get_bid(self):
        return self._bids.max_key()

    def get_bids(self, price):
        return self._bids.get(price)

    def remove_bids(self, price):
        self._bids.remove(price)

    def set_bids(self, price, bids):
        price = round(price, 8)
        bids = round (bids, 8)
        log.debug ("set_bid: price: %g size: %g" % (price, bids))
        self._bids.insert(price, bids)  # insert on RBtree is a replace for existing keys
                                                            
#EOF