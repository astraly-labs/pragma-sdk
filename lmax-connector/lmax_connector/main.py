import asyncio
import os
import signal
import time
import quickfix as fix
from dotenv import load_dotenv
import requests

from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.entry import (
    InstrumentType,
    OrderbookData,
    OrderbookEntry,
    OrderbookUpdateType,
    SpotEntry,
    FutureEntry,
)
from pragma_sdk.common.logging import get_pragma_sdk_logger

from faucon import FauconEnvironment, FauconProducerBuilder, FauconTopic
from faucon.topics.topics import PriceEntryTopic, OrderbookEntryTopic

logger = get_pragma_sdk_logger()


# Add extension methods to SpotEntry for Faucon integration
def spot_entry_to_faucon_topic(self) -> FauconTopic:
    """Return the topic for price entries."""
    return PriceEntryTopic.to_faucon_topic()


def spot_entry_to_faucon_key(self) -> str:
    """Generate key for price entry."""
    return PriceEntryTopic.to_faucon_key(self)


def future_entry_to_faucon_topic(self) -> FauconTopic:
    """Return the topic for price entries."""
    return PriceEntryTopic.to_faucon_topic()


def future_entry_to_faucon_key(self) -> str:
    """Generate key for price entry."""
    return PriceEntryTopic.to_faucon_key(self)


# Monkey patch the methods onto the classes
SpotEntry.to_faucon_topic = spot_entry_to_faucon_topic
SpotEntry.to_faucon_key = spot_entry_to_faucon_key
FutureEntry.to_faucon_topic = future_entry_to_faucon_topic
FutureEntry.to_faucon_key = future_entry_to_faucon_key


# Define constants for LMAX instrument IDs
LMAX_INSTRUMENT_IDS = {
    "EUR/USD": "4001",
    "XAU/USD": "100637",  # Gold Spot
    "SPX500m": "110093",  # US SPX 500 Mini
    "XBR/USD": "100805",  # UK Brent Spot
    "TECH100m": "110095",  # US Tech 100 Mini
    "USD/JPY": "4004",  # US Dollar/Japanese Yen
    "XAG/USD": "100639",  # Silver Spot
}

# Define mapping between LMAX security IDs and symbols
SECURITY_ID_TO_SYMBOL = {
    "4001": "EUR/USD",
    "100637": "XAU/USD",
    "110093": "SPX500m",
    "100805": "XBR/USD",
    "110095": "TECH100m",
    "4004": "USD/JPY",
    "100639": "XAG/USD",
}


class OrderbookEntryWrapper(OrderbookEntry):
    def to_faucon_topic(self):
        return OrderbookEntryTopic.to_faucon_topic()

    def to_faucon_key(self):
        return OrderbookEntryTopic.to_faucon_key(self)


class SpotEntryWrapper(SpotEntry):
    def to_faucon_topic(self):
        return PriceEntryTopic.to_faucon_topic()

    def to_faucon_key(self):
        return PriceEntryTopic.to_faucon_key(self)


class LmaxFixApplication(fix.Application):
    def __init__(self):
        super().__init__()
        self.latest_market_data = {}
        self.session_ready = asyncio.Event()
        self.market_data_ready = {}
        self.last_subscription_time = 0  # Track when we last subscribed

    def onCreate(self, sessionID):
        logger.info("Session created: %s", sessionID)

    def onLogon(self, sessionID):
        logger.info("Logged on: %s", sessionID)
        # Reset session ready event
        self.session_ready.clear()  # Clear first to ensure any waiters see the new state
        self.session_ready.set()
        # Force immediate resubscription after logon
        self.last_subscription_time = 0

    def onLogout(self, sessionID):
        logger.info("Logged out: %s", sessionID)
        self.session_ready.clear()
        # Clear last subscription time to force resubscription on next logon
        self.last_subscription_time = 0

    def fromAdmin(self, message, sessionID):
        """Log admin messages received from LMAX"""
        try:
            msgType = fix.MsgType()
            message.getHeader().getField(msgType)

            logger.debug(f"Received admin message: {message.toString()}")

            if msgType.getValue() == fix.MsgType_Reject:
                self._fromAdmin10(message)
            elif msgType.getValue() == fix.MsgType_Logon:
                logger.info("Received Logon message")
            elif msgType.getValue() == fix.MsgType_Heartbeat:
                logger.debug("Received Heartbeat")
            elif msgType.getValue() == fix.MsgType_TestRequest:
                logger.info("Received Test Request - QuickFIX should auto-respond")
        except Exception as e:
            logger.error(
                f"Error processing admin message: {str(e)}, Message: {message.toString()}"
            )

    def _fromAdmin10(self, message):
        refMsgType = fix.RefMsgType()
        message.getField(refMsgType)
        refSeqNum = fix.RefSeqNum()
        message.getField(refSeqNum)
        text = fix.Text()
        message.getField(text)
        logger.error(
            f"Message Rejected - Type: {refMsgType.getValue()}, SeqNum: {refSeqNum.getValue()}, Text: {text.getValue()}"
        )

    def toAdmin(self, message, sessionID):
        """Log admin messages sent to LMAX"""
        try:
            msgType = fix.MsgType()
            message.getHeader().getField(msgType)

            if msgType.getValue() == fix.MsgType_Logon:
                self._toAdmin_9(message)
            else:
                logger.debug(f"Sending admin message: {message.toString()}")
        except Exception as e:
            logger.error(f"Error preparing admin message: {str(e)}")

    def _toAdmin_9(self, message):
        # Required fields for LMAX logon
        message.setField(fix.EncryptMethod(0))  # No encryption
        message.setField(fix.HeartBtInt(30))
        message.setField(fix.Username(self.username))  # Tag 553
        message.setField(fix.Password(self.password))  # Tag 554
        message.setField(fix.ResetSeqNumFlag(True))  # Tag 141
        logger.info(f"Sending Logon message: {message.toString()}")

    def onError(self, sessionID):
        """Log FIX session errors"""
        logger.error(f"FIX Session Error for {sessionID}")

    def fromApp(self, message, sessionID):
        try:
            msgType = fix.MsgType()
            message.getHeader().getField(msgType)

            if msgType.getValue() == fix.MsgType_MarketDataSnapshotFullRefresh:
                logger.debug("Received market data snapshot")
                try:
                    self._handle_market_data(message)
                except fix.FieldNotFound as e:
                    logger.error(f"Field not found in market data message: {str(e)}")
                except Exception as e:
                    logger.error(f"Error handling market data: {str(e)}")
            else:
                logger.info(
                    f"Received application message - Type: {msgType.getValue()}, Content: {message.toString()}"
                )
        except fix.FieldNotFound as e:
            logger.error(f"Field not found in message header: {str(e)}")
        except Exception as e:
            logger.error(f"Error processing application message: {str(e)}")

    def toApp(self, message, sessionID):
        """Log outgoing application messages"""
        logger.info(f"Sending application message: {message.toString()}")

    def _handle_market_data(self, message):
        # Log the raw FIX message to debug the market depth issue
        logger.info(f"Raw market data message: {message.toString()}")

        security_id = fix.SecurityID()
        message.getField(security_id)
        security_id = security_id.getValue()
        logger.debug(f"Processing market data for security ID {security_id}")

        bids = []
        asks = []
        noMDEntries = fix.NoMDEntries()
        message.getField(noMDEntries)

        num_entries = noMDEntries.getValue()
        logger.info(f"Number of entries: {num_entries}")

        for i in range(num_entries):
            # NoMDEntries is 268, MDEntryType is 269
            group = fix.Group(268, 269)
            message.getGroup(i + 1, group)

            mdEntryType = fix.MDEntryType()
            group.getField(mdEntryType)

            mdEntryPx = fix.MDEntryPx()
            group.getField(mdEntryPx)

            mdEntrySize = fix.MDEntrySize()
            group.getField(mdEntrySize)

            if mdEntryType.getValue() == fix.MDEntryType_BID:
                bid = float(mdEntryPx.getValue())
                bid_size = float(mdEntrySize.getValue())
                bids.append((bid, bid_size))
                logger.debug(f"Got bid: {bid}")
            elif mdEntryType.getValue() == fix.MDEntryType_OFFER:
                ask = float(mdEntryPx.getValue())
                ask_size = float(mdEntrySize.getValue())
                asks.append((ask, ask_size))
                logger.debug(f"Got ask: {ask}")

        if bids and asks:
            if symbol := SECURITY_ID_TO_SYMBOL.get(security_id):
                self.latest_market_data[symbol] = {
                    "bids": bids,
                    "asks": asks,
                    "timestamp": int(time.time()),
                }
                logger.info(f"Updated {symbol} price - Bid: {bids}, Ask: {asks}")
                if symbol in self.market_data_ready:
                    self.market_data_ready[symbol].set()
            else:
                logger.warning(f"Received data for unknown security ID: {security_id}")


class LmaxConnector:
    def __init__(self, faucon_producer):
        self.faucon_producer = faucon_producer
        self.running = True
        self.last_known_prices = {}  # Store last known prices for each symbol

        # Create required directories
        os.makedirs("config", exist_ok=True)
        os.makedirs("store", exist_ok=True)
        os.makedirs("log", exist_ok=True)

        # Write FIX settings to file
        self.fix_config_path = "config/fix_settings.cfg"
        fix_settings = f"""[DEFAULT]
ConnectionType=initiator
ReconnectInterval=2
FileStorePath=store
FileLogPath=log
StartTime=00:00:00
EndTime=00:00:00
UseDataDictionary=Y
DataDictionary=config/Fix44.xml
ValidateUserDefinedFields=N
ValidateIncomingMessage=N
RefreshOnLogon=Y
SocketUseSSL=Y
LogoutTimeout=5
ResetOnLogon=Y
ResetOnLogout=Y
ResetOnDisconnect=Y
SendRedundantResendRequests=Y
PersistMessages=Y

[SESSION]
BeginString=FIX.4.4
SenderCompID={os.getenv('LMAX_SENDER_COMP_ID')}
TargetCompID={os.getenv('LMAX_TARGET_COMP_ID')}
SocketConnectHost=127.0.0.1
SocketConnectPort=40003
Password={os.getenv('LMAX_PASSWORD')}
HeartBtInt=30"""

        logger.info(f"Using FIX settings:\n{fix_settings}")
        with open(self.fix_config_path, "w") as f:
            f.write(fix_settings)

        self.application = LmaxFixApplication()
        self.init_fix()

    async def seed_initial_prices(self, pairs):
        """
        Seed last-known and latest market prices using the public Extended Exchange
        REST API when LMAX provides no data (e.g. weekends).
        """
        EXTENDED_API_BASE_URL = "https://api.extended.exchange/api/v1"
        EXTENDED_MARKET_MAPPING = {
            "EUR/USD": "EUR-USD",
            "XAU/USD": "XAU-USD",
            "SPX500m": "SPX500m-USD",
            "XBR/USD": "XBR-USD",
            "TECH100m": "TECH100m-USD",
            "USD/JPY": "USD-JPY",
            "XAG/USD": "XAG-USD",
        }

        for symbol in pairs:
            market = EXTENDED_MARKET_MAPPING.get(symbol)
            if not market:
                logger.warning(f"No Extended Exchange mapping for {symbol}")
                continue

            url = f"{EXTENDED_API_BASE_URL}/info/markets"
            try:
                response = await asyncio.to_thread(
                    requests.get, url, params={"market": market}, timeout=10
                )
                if response.status_code != 200:
                    logger.warning(
                        f"Extended API request for {symbol} returned HTTP "
                        f"{response.status_code}"
                    )
                    continue

                payload = response.json()
                stats = (
                    payload.get("data", [{}])[0]
                    .get("marketStats", {})
                    .get("indexPrice")
                )
                if stats is None:
                    logger.warning(
                        f"Extended API response missing indexPrice for {symbol}"
                    )
                    continue

                price = float(stats)
                price_data = {
                    "bids": [price],
                    "asks": [price],
                    "timestamp": int(time.time()),
                }
                self.last_known_prices[symbol] = price_data.copy()
                self.application.latest_market_data[symbol] = price_data.copy()
                logger.info(
                    f"Seeded {symbol} with indexPrice {price} from Extended Exchange"
                )
            except Exception as e:
                logger.error(f"Error seeding {symbol} from Extended API: {e}")

        # brief delay so downstream tasks can pick the seeded data up
        await asyncio.sleep(0.1)

    def init_fix(self):
        settings = fix.SessionSettings(self.fix_config_path)
        store_factory = fix.FileStoreFactory(settings)
        log_factory = fix.FileLogFactory(settings)

        # Initialize application with credentials
        self.application.username = os.getenv("LMAX_SENDER_COMP_ID")
        self.application.password = os.getenv("LMAX_PASSWORD")

        # Start initiator
        try:
            self.initiator = fix.SocketInitiator(
                self.application, store_factory, settings, log_factory
            )
            self.initiator.start()
            logger.info("FIX initiator started successfully")
        except Exception as e:
            logger.error(f"Failed to start FIX initiator: {str(e)}")
            raise

    async def subscribe_market_data(self, pairs):
        """Subscribe to market data for specific pairs"""
        logger.info("Waiting for session to be ready...")
        try:
            # Get credentials
            sender_comp_id = os.getenv("LMAX_SENDER_COMP_ID")
            target_comp_id = os.getenv("LMAX_TARGET_COMP_ID")

            # Create market data request
            message = fix.Message()
            header = message.getHeader()

            # Set header fields in order
            header.setField(fix.BeginString("FIX.4.4"))
            header.setField(fix.MsgType(fix.MsgType_MarketDataRequest))  # 'V'
            header.setField(fix.SenderCompID(sender_comp_id))
            header.setField(fix.TargetCompID(target_comp_id))

            # Required fields for market data request in ascending tag order
            message.setField(fix.MDReqID("1"))  # Tag 262
            message.setField(fix.SubscriptionRequestType("1"))  # Tag 263
            message.setField(fix.MarketDepth(10))  # Tag 264
            message.setField(fix.NoMDEntryTypes(2))  # Tag 267

            # Add entry types group (267)
            for entry_type in ["0", "1"]:  # 0=Bid, 1=Offer
                group = fix.Group(267, 269)
                group.setField(fix.MDEntryType(entry_type))  # Tag 269
                message.addGroup(group)

            # Get LMAX symbols for the requested pairs
            pair_symbols = []
            for pair in pairs:
                if isinstance(pair, Pair):
                    pair_id = f"{pair.base_currency.id}/{pair.quote_currency.id}"
                else:
                    pair_id = pair  # Assuming pair is already a string like "XAU/USD"

                if pair_id in LMAX_INSTRUMENT_IDS:
                    pair_symbols.append((pair_id, LMAX_INSTRUMENT_IDS[pair_id]))
                else:
                    logger.warning(f"No LMAX instrument ID found for pair {pair_id}")

            if not pair_symbols:
                logger.error("No valid pairs to subscribe")
                return

            # Log the pairs we're subscribing to
            logger.info(
                f"Subscribing to the following pairs: {[p[0] for p in pair_symbols]}"
            )

            # Set NoRelatedSym count
            message.setField(fix.NoRelatedSym(len(pair_symbols)))  # Tag 146

            # Add instrument groups
            for pair_id, security_id in pair_symbols:
                instrument_group = fix.Group(
                    146, 48
                )  # 146 = NoRelatedSym, 48 = SecurityID
                instrument_group.setField(fix.SecurityID(security_id))  # Tag 48
                instrument_group.setField(
                    fix.SecurityIDSource("8")
                )  # Tag 22, "8" = Exchange Symbol
                message.addGroup(instrument_group)
                logger.debug(
                    f"Added instrument {pair_id} with security ID {security_id}"
                )

            # Create session ID for sending
            session_id = fix.SessionID("FIX.4.4", sender_comp_id, target_comp_id)

            # Keep the subscription task alive and monitor session
            resubscribe_interval = 30  # Resubscribe every 30 seconds
            reconnect_delay = 2  # Wait 2 seconds between reconnection attempts
            last_error_time = 0
            error_threshold = 5  # Maximum number of errors in error_window
            error_window = 60  # Time window for counting errors in seconds
            error_count = 0

            while self.running:
                try:
                    current_time = time.time()

                    # Reset error count if we're outside the error window
                    if current_time - last_error_time > error_window:
                        error_count = 0

                    # Check if session is ready
                    if not self.application.session_ready.is_set():
                        logger.warning(
                            "Session disconnected, waiting for reconnection..."
                        )
                        try:
                            # Wait for session with timeout
                            await asyncio.wait_for(
                                self.application.session_ready.wait(), timeout=5.0
                            )
                            logger.info(
                                "Session reconnected, forcing resubscription..."
                            )
                            # Force immediate resubscription
                            if not fix.Session.sendToTarget(message, session_id):
                                raise Exception(
                                    "Failed to send market data request after reconnection"
                                )
                            self.application.last_subscription_time = current_time
                            logger.info(
                                "Market data request sent successfully after reconnection"
                            )
                        except asyncio.TimeoutError:
                            logger.error("Timeout waiting for session reconnection")
                            await asyncio.sleep(reconnect_delay)
                            continue
                        except Exception as e:
                            logger.error(f"Error during reconnection: {str(e)}")
                            error_count += 1
                            last_error_time = current_time
                            if error_count >= error_threshold:
                                logger.error("Too many errors, restarting session...")
                                self.initiator.stop()
                                await asyncio.sleep(reconnect_delay)
                                self.initiator.start()
                                error_count = 0
                            await asyncio.sleep(reconnect_delay)
                            continue

                    # Subscribe/resubscribe if needed
                    if (
                        current_time - self.application.last_subscription_time
                        >= resubscribe_interval
                    ):
                        logger.info("Sending market data request...")
                        try:
                            if not fix.Session.sendToTarget(message, session_id):
                                raise Exception("Failed to send market data request")
                            self.application.last_subscription_time = current_time
                            logger.info("Market data request sent successfully")
                        except Exception as e:
                            logger.error(f"Error sending market data request: {str(e)}")
                            error_count += 1
                            last_error_time = current_time
                            if error_count >= error_threshold:
                                logger.error("Too many errors, restarting session...")
                                self.initiator.stop()
                                await asyncio.sleep(reconnect_delay)
                                self.initiator.start()
                                error_count = 0
                            await asyncio.sleep(reconnect_delay)
                            continue

                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Error in subscription loop: {str(e)}")
                    error_count += 1
                    last_error_time = current_time
                    await asyncio.sleep(reconnect_delay)

        except Exception as e:
            logger.error(f"Fatal error in market data subscription: {str(e)}")
            raise

    async def push_prices(self, pair):
        """Push prices for a specific pair to Pragma"""
        try:
            # First, ensure we have a string representation
            if isinstance(pair, Pair):
                symbol = f"{pair.base_currency.id}/{pair.quote_currency.id}"
                pair_obj = pair
            else:
                symbol = pair

                try:
                    # Handle each type of instrument explicitly
                    if symbol == "EUR/USD":
                        logger.debug(f"Creating pair for {symbol}")
                        pair_obj = Pair.from_tickers("EUR", "USD")
                    elif symbol == "USD/JPY":
                        logger.debug(f"Creating pair for {symbol}")
                        pair_obj = Pair.from_tickers("USD", "JPY")
                    elif symbol == "XAU/USD":
                        logger.debug(f"Creating pair for {symbol}")
                        pair_obj = Pair.from_tickers("XAU", "USD")
                    elif symbol == "XBR/USD":
                        logger.debug(f"Creating pair for {symbol}")
                        pair_obj = Pair.from_tickers("XBR", "USD")
                    elif symbol == "SPX500m":
                        logger.debug(f"Creating special pair for {symbol}")
                        # For indices, use the symbol directly
                        pair_obj = Pair.from_tickers("SPX500", "USD")
                        pair_obj.id = symbol  # Use the symbol directly as the ID
                    elif symbol == "TECH100m":
                        logger.debug(f"Creating special pair for {symbol}")
                        # For indices, use the symbol directly
                        pair_obj = Pair.from_tickers("TECH100m", "USD")
                        pair_obj.id = symbol  # Use the symbol directly as the ID
                    elif symbol == "XAG/USD":
                        logger.debug(f"Creating pair for {symbol}")
                        pair_obj = Pair.from_tickers("XAG", "USD")
                    else:
                        logger.error(f"Unknown instrument: {symbol}")
                        # Try a generic approach as fallback
                        if "/" in symbol:
                            base, quote = symbol.split("/")
                            pair_obj = Pair.from_tickers(base, quote)
                        else:
                            # Last resort for special instruments
                            pair_obj = Pair.from_tickers(symbol, "USD")
                            pair_obj.id = symbol
                except Exception as e:
                    logger.error(f"Error creating pair object for {symbol}: {str(e)}")
                    # Create a minimal pair object that will work
                    pair_obj = Pair.from_tickers(
                        "EUR", "USD"
                    )  # Use a known working pair as a template
                    if "/" in symbol:
                        base, quote = symbol.split("/")
                        pair_obj.id = f"{base}/{quote}"
                    else:
                        pair_obj.id = symbol

            logger.info(
                f"Starting price push loop for {symbol} with pair ID: {pair_obj.id}"
            )
            logger.info(f"Starting price push loop for {symbol}")

            # Create event for this symbol if it doesn't exist
            if symbol not in self.application.market_data_ready:
                self.application.market_data_ready[symbol] = asyncio.Event()

            while self.running:
                try:
                    # Try to get new market data with a timeout
                    try:
                        await asyncio.wait_for(
                            self.application.market_data_ready[symbol].wait(),
                            timeout=30,  # Wait up to 30 seconds for new data
                        )
                        self.application.market_data_ready[
                            symbol
                        ].clear()  # Reset for next update

                        if market_data := self.application.latest_market_data.get(
                            symbol
                        ):
                            # Store the new data as the last known price
                            self.last_known_prices[symbol] = market_data.copy()
                    except asyncio.TimeoutError:
                        logger.info(
                            f"No new data received for {symbol} in 30 seconds, using last known price"
                        )

                    if market_data := self.application.latest_market_data.get(
                        symbol
                    ) or self.last_known_prices.get(symbol):
                        bids = market_data["bids"]
                        asks = market_data["asks"]
                        # Calculate mid price from best bid and ask
                        if bids and asks:
                            best_bid = bids[0][0]  # Get price from (price, size) tuple
                            best_ask = asks[0][0]  # Get price from (price, size) tuple
                            mid_price = (best_bid + best_ask) / 2
                        elif bids:
                            mid_price = bids[0][0]
                        elif asks:
                            mid_price = asks[0][0]
                        else:
                            logger.warning(f"No bids or asks for {symbol}")
                            continue

                        timestamp = int(
                            time.time()
                        )  # Use current timestamp for last known prices
                        price_int = int(mid_price * 10**18)
                        pair_id = pair_obj.id

                        ob_entry = OrderbookEntryWrapper(
                            source="LMAX",
                            instrument_type=InstrumentType.SPOT,
                            pair=pair_obj,
                            type=OrderbookUpdateType.SNAPSHOT,
                            data=OrderbookData(
                                update_id=timestamp,
                                bids=bids,
                                asks=asks,
                            ),
                            timestamp_ms=timestamp,
                        )

                        spot_entry = SpotEntryWrapper(
                            pair_id=pair_id,
                            price=price_int,
                            timestamp=timestamp,
                            source="LMAX",
                            publisher=os.getenv("PRAGMA_PUBLISHER_ID"),
                            volume=0,
                        )

                        try:
                            # Send the orderbook entry to Kafka via Faucon
                            partition, offset = await self.faucon_producer.send(
                                ob_entry
                            )
                            # # We also send the spot entry to Kafka
                            partition, offset = await self.faucon_producer.send(
                                spot_entry
                            )

                            logger.info(
                                f"Successfully pushed {symbol} pair_id {pair_id} price {mid_price} to Kafka"
                            )
                            logger.info(f"  Topic: {ob_entry.to_faucon_topic()}")
                            logger.info(f"  Key: {ob_entry.to_faucon_key()}")
                            # logger.info(f"  Partition: {partition}")
                            # logger.info(f"  Offset: {offset}")
                        except Exception as e:
                            logger.error(
                                f"Error publishing {symbol} to Kafka: {str(e)}"
                            )
                            # Don't raise, just log and continue
                            await asyncio.sleep(5)  # Back off before retrying
                    else:
                        logger.debug(f"No market data available yet for {symbol}")
                        await asyncio.sleep(
                            5
                        )  # Wait before retrying if no data is available
                except Exception as e:
                    logger.error(f"Error pushing price: {str(e)}", exc_info=True)
                    await asyncio.sleep(5)  # Back off on error

        except Exception as e:
            logger.error(f"Error pushing prices: {str(e)}")

    def stop(self):
        self.running = False
        if hasattr(self, "initiator"):
            self.initiator.stop()
        # Close Faucon producer
        if hasattr(self, "faucon_producer"):
            self.faucon_producer.close()
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

    broker_address = os.getenv("PRAGMA_BROKER_ADDRESS")
    print(f"Broker address: {broker_address}")
    # Initialize Faucon producer
    logger.info("Initializing Faucon producer...")
    producer = FauconProducerBuilder.from_environment(
        FauconEnvironment.custom(broker_address=broker_address)
    ).build()

    # Configure pairs to fetch
    # You can specify either as string IDs or create Pair objects
    requested_pairs = [
        "EUR/USD",
        # "XAU/USD",
        # "SPX500m",
        # "XBR/USD",
        # "TECH100m",
        # "USD/JPY",
        # "XAG/USD",
    ]
    logger.info(f"Configured to fetch {requested_pairs} from LMAX")

    # Initialize LMAX connector
    logger.info("Initializing LMAX FIX connection...")
    connector = LmaxConnector(producer)

    # Seed prices from Extended Exchange before entering the main loops
    await connector.seed_initial_prices(requested_pairs)

    # Handle graceful shutdown
    loop = asyncio.get_event_loop()
    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(
            s, lambda s=s: asyncio.create_task(shutdown(s, loop, connector))
        )
    logger.info("Registered shutdown handlers")

    try:
        # Create subscription task for all pairs
        subscription_task = asyncio.create_task(
            connector.subscribe_market_data(requested_pairs)
        )

        # Create price pushing tasks for each pair with explicit logging
        push_tasks = []
        for pair in requested_pairs:
            logger.info(f"Creating price push task for pair: {pair}")
            task = asyncio.create_task(connector.push_prices(pair))
            task.set_name(f"push_prices_{pair}")
            push_tasks.append(task)

        logger.info(f"Created {len(push_tasks)} price push tasks")

        # Wait for all tasks to complete or be cancelled
        await asyncio.gather(subscription_task, *push_tasks, return_exceptions=True)
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
