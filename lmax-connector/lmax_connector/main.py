import asyncio
import os
import signal
import time
from typing import Optional
import quickfix as fix
from dotenv import load_dotenv
import shutil

from pragma_sdk.offchain.client import PragmaAPIClient
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.entry import SpotEntry
from pragma_sdk.common.logging import get_pragma_sdk_logger

logger = get_pragma_sdk_logger()

class LmaxFixApplication(fix.Application):
    def __init__(self):
        super().__init__()
        self.latest_market_data = {}
        self.session_ready = asyncio.Event()
        self.market_data_ready = {}

    def onCreate(self, sessionID):
        logger.info("Session created: %s", sessionID)

    def onLogon(self, sessionID):
        logger.info("Logged on: %s", sessionID)
        self.session_ready.set()

    def onLogout(self, sessionID):
        logger.info("Logged out: %s", sessionID)
        self.session_ready.clear()

    def fromAdmin(self, message, sessionID):
        """Log admin messages received from LMAX"""
        try:
            msgType = fix.MsgType()
            message.getHeader().getField(msgType)
            
            logger.debug(f"Received admin message: {message.toString()}")
            
            if msgType.getValue() == fix.MsgType_Reject:
                refMsgType = fix.RefMsgType()
                message.getField(refMsgType)
                refSeqNum = fix.RefSeqNum()
                message.getField(refSeqNum)
                text = fix.Text()
                message.getField(text)
                logger.error(f"Message Rejected - Type: {refMsgType.getValue()}, SeqNum: {refSeqNum.getValue()}, Text: {text.getValue()}")
            elif msgType.getValue() == fix.MsgType_Logon:
                logger.info("Received Logon message")
            elif msgType.getValue() == fix.MsgType_Heartbeat:
                logger.debug("Received Heartbeat")
        except Exception as e:
            logger.error(f"Error processing admin message: {str(e)}, Message: {message.toString()}")

    def toAdmin(self, message, sessionID):
        """Log admin messages sent to LMAX"""
        try:
            msgType = fix.MsgType()
            message.getHeader().getField(msgType)
            
            if msgType.getValue() == fix.MsgType_Logon:
                # Required fields for LMAX logon
                message.setField(fix.EncryptMethod(0))  # No encryption
                message.setField(fix.HeartBtInt(30))
                message.setField(fix.Username(self.username))  # Tag 553
                message.setField(fix.Password(self.password))  # Tag 554
                message.setField(fix.ResetSeqNumFlag(True))  # Tag 141
                logger.info(f"Sending Logon message: {message.toString()}")
            else:
                logger.debug(f"Sending admin message: {message.toString()}")
        except Exception as e:
            logger.error(f"Error preparing admin message: {str(e)}")

    def onError(self, sessionID):
        """Log FIX session errors"""
        logger.error(f"FIX Session Error for {sessionID}")

    def fromApp(self, message, sessionID):
        msgType = fix.MsgType()
        message.getHeader().getField(msgType)
        
        if msgType.getValue() == fix.MsgType_MarketDataSnapshotFullRefresh:
            logger.debug("Received market data snapshot")
            self._handle_market_data(message)
        else:
            logger.info(f"Received application message - Type: {msgType.getValue()}, Content: {message.toString()}")

    def toApp(self, message, sessionID):
        """Log outgoing application messages"""
        logger.info(f"Sending application message: {message.toString()}")

    def _handle_market_data(self, message):
        symbol = fix.Symbol()
        message.getField(symbol)
        symbol = symbol.getValue()
        logger.debug(f"Processing market data for {symbol}")
        
        bid = ask = None
        noMDEntries = fix.NoMDEntries()
        message.getField(noMDEntries)
        
        for i in range(noMDEntries.getValue()):
            group = fix.Group(fix.FIELD.NoMDEntries, fix.FIELD.MDEntryType)
            message.getGroup(i + 1, group)
            
            mdEntryType = fix.MDEntryType()
            group.getField(mdEntryType)
            
            mdEntryPx = fix.MDEntryPx()
            group.getField(mdEntryPx)
            
            if mdEntryType.getValue() == fix.MDEntryType_BID:
                bid = float(mdEntryPx.getValue())
                logger.debug(f"Got bid: {bid}")
            elif mdEntryType.getValue() == fix.MDEntryType_OFFER:
                ask = float(mdEntryPx.getValue())
                logger.debug(f"Got ask: {ask}")
        
        if bid is not None and ask is not None:
            self.latest_market_data[symbol] = {
                "bid": bid,
                "ask": ask,
                "timestamp": int(time.time())
            }
            logger.info(f"Updated {symbol} price - Bid: {bid}, Ask: {ask}")
            if symbol in self.market_data_ready:
                self.market_data_ready[symbol].set()

class LmaxConnector:
    def __init__(self, pragma_client: PragmaAPIClient):
        self.pragma_client = pragma_client
        self.running = True
        
        # Create required directories
        os.makedirs("config", exist_ok=True)
        os.makedirs("store", exist_ok=True)
        os.makedirs("log", exist_ok=True)
        
        # Copy data dictionary
        dict_path = "config/FIX44.xml"
        
        # Write FIX settings to file
        self.fix_config_path = "config/fix_settings.cfg"
        fix_settings = f"""[DEFAULT]
ConnectionType=initiator
ReconnectInterval=60
FileStorePath=store
FileLogPath=log
StartTime=00:00:00
EndTime=00:00:00
UseDataDictionary=N
ValidateUserDefinedFields=N
ValidateIncomingMessage=N
RefreshOnLogon=Y
SocketUseSSL=Y

[SESSION]
BeginString=FIX.4.4
SenderCompID={os.getenv('LMAX_SENDER_COMP_ID')}
TargetCompID={os.getenv('LMAX_TARGET_COMP_ID')}
SocketConnectHost=127.0.0.1
SocketConnectPort=40003
Password={os.getenv('LMAX_PASSWORD')}
ResetOnLogon=Y
HeartBtInt=30"""

        logger.info(f"Using FIX settings:\n{fix_settings}")
        with open(self.fix_config_path, "w") as f:
            f.write(fix_settings)
            
        self.application = LmaxFixApplication()
        self.init_fix()

    def init_fix(self):
        settings = fix.SessionSettings(self.fix_config_path)
        store_factory = fix.FileStoreFactory(settings)
        log_factory = fix.FileLogFactory(settings)
        
        # Initialize application with credentials
        self.application.username = os.getenv('LMAX_SENDER_COMP_ID')
        self.application.password = os.getenv('LMAX_PASSWORD')
        
        # Start initiator
        try:
            self.initiator = fix.SocketInitiator(
                self.application,
                store_factory,
                settings,
                log_factory
            )
            self.initiator.start()
            logger.info("FIX initiator started successfully")
        except Exception as e:
            logger.error(f"Failed to start FIX initiator: {str(e)}")
            raise

    async def subscribe_market_data(self, pair: Pair):
        """Subscribe to market data for a specific pair"""
        logger.info("Waiting for session to be ready...")
        try:
            # Wait for session with timeout
            ready = await asyncio.wait_for(self.application.session_ready.wait(), timeout=10.0)
            if not ready:
                raise Exception("Session not ready after timeout")
            logger.info("Session ready, sending market data request")
            
            # Create market data request
            message = fix.Message()
            header = message.getHeader()
            header.setField(fix.MsgType(fix.MsgType_MarketDataRequest))
            
            # Required fields as per LMAX example
            message.setField(fix.MDReqID("EUR/USD"))  # Unique request ID
            message.setField(fix.SubscriptionRequestType('1'))  # 1 = SNAPSHOTUPDATE
            message.setField(fix.MarketDepth(0))  # Full book
            message.setField(fix.MDUpdateType(0))  # Full refresh
            message.setField(fix.NoMDEntryTypes(2))
            
            # Add entry types group
            group = fix.Group(fix.FIELD.NoMDEntryTypes, fix.FIELD.MDEntryType)
            group.setField(fix.MDEntryType('0'))  # Bid
            message.addGroup(group)
            group = fix.Group(fix.FIELD.NoMDEntryTypes, fix.FIELD.MDEntryType)
            group.setField(fix.MDEntryType('1'))  # Offer
            message.addGroup(group)
            
            # Add instrument group
            message.setField(fix.NoRelatedSym(1))
            message.setField(fix.Symbol("4001"))  # EUR/USD instrument ID
            message.setField(fix.SecurityType("8"))  # FX
            
            logger.info(f"Sending market data request: {message.toString()}")
            if not fix.Session.sendToTarget(message):
                raise Exception("Failed to send market data request")
            logger.info("Market data request sent successfully")
            
        except asyncio.TimeoutError:
            logger.error("Timeout waiting for session to be ready")
            raise
        except Exception as e:
            logger.error(f"Failed to subscribe to market data: {str(e)}")
            raise

    async def push_prices(self, pair: Pair):
        symbol = f"{pair.base_currency.id}/{pair.quote_currency.id}"
        logger.info(f"Starting price push loop for {symbol}")
        while self.running:
            try:
                market_data = self.application.latest_market_data.get(symbol)
                if market_data:
                    bid, ask = market_data["bid"], market_data["ask"]
                    price = (bid + ask) / 2
                    timestamp = market_data["timestamp"]
                    price_int = int(price * (10 ** pair.decimals()))
                    
                    entry = SpotEntry(
                        pair_id=pair.id,
                        price=price_int,
                        timestamp=timestamp,
                        source="LMAX",
                        publisher=os.getenv("PRAGMA_PUBLISHER_ID"),
                        volume=0,
                    )
                    
                    await self.pragma_client.push_entry(entry)
                    logger.info(f"Pushed {pair} price {price} to Pragma")
                else:
                    logger.debug(f"No market data available for {symbol}")
                
                await asyncio.sleep(1)  # Adjust frequency as needed
            except Exception as e:
                logger.error(f"Error pushing price: {str(e)}")
                await asyncio.sleep(5)  # Back off on error

    def stop(self):
        self.running = False
        if hasattr(self, 'initiator'):
            self.initiator.stop()
        # Clean up config file
        if os.path.exists(self.fix_config_path):
            os.remove(self.fix_config_path)

async def shutdown(sig, loop, connector):
    logger.info(f"Received exit signal {sig.name}...")
    connector.stop()
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    logger.info(f"Cancelling {len(tasks)} outstanding tasks")
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        pass
    finally:
        loop.call_soon_threadsafe(loop.stop)

async def main():
    logger.info("Starting LMAX Connector service...")
    load_dotenv()
    
    # Initialize Pragma client
    logger.info("Initializing Pragma client...")
    pragma_client = PragmaAPIClient(
        api_key=os.getenv("PRAGMA_API_KEY"),
        api_base_url=os.getenv("PRAGMA_API_BASE_URL"),
        account_private_key=os.getenv("PRAGMA_ACCOUNT_PRIVATE_KEY"),
        account_contract_address=os.getenv("PRAGMA_ACCOUNT_CONTRACT_ADDRESS")
    )
    
    # Create EUR/USD pair
    pair = Pair.from_tickers("EUR", "USD")
    logger.info(f"Configured to fetch {pair} from LMAX")
    
    # Initialize LMAX connector
    logger.info("Initializing LMAX FIX connection...")
    connector = LmaxConnector(pragma_client)
    
    # Handle graceful shutdown
    loop = asyncio.get_event_loop()
    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(
            s, lambda s=s: asyncio.create_task(shutdown(s, loop, connector))
        )
    logger.info("Registered shutdown handlers")
    
    try:
        # Subscribe to market data
        logger.info("Subscribing to market data...")
        await connector.subscribe_market_data(pair)
        
        # Start pushing prices
        logger.info("Starting price push loop...")
        await connector.push_prices(pair)
    except asyncio.CancelledError:
        logger.info("Service shutdown requested")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        raise
    finally:
        logger.info("Stopping connector...")
        connector.stop()

if __name__ == "__main__":
    asyncio.run(main()) 