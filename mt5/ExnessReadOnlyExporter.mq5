//+------------------------------------------------------------------+
//| V9 Exness MT5 Read-Only Exporter                                 |
//| Exports Market Watch Gold and Forex snapshots to Common Files.   |
//| NO order, position, or account modification functions are used.  |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs

input string InpAccountType = "Raw Spread";
input int InpCandleCount = 100;
input string InpOutputFile = "v9_mt5_readonly_snapshot.json";

string IsoUtc(datetime value)
{
   string result = TimeToString(value, TIME_DATE|TIME_SECONDS);
   StringReplace(result, ".", "-");
   StringReplace(result, " ", "T");
   return result + "Z";
}

bool IsEligibleSymbol(string symbol, string &market_type,
                      string &base_currency, string &quote_currency)
{
   base_currency = SymbolInfoString(symbol, SYMBOL_CURRENCY_BASE);
   quote_currency = SymbolInfoString(symbol, SYMBOL_CURRENCY_PROFIT);

   if(StringLen(base_currency) != 3 || StringLen(quote_currency) != 3)
      return false;

   if(base_currency == "XAU")
   {
      market_type = "METAL";
      return true;
   }

   // Exclude metals other than Gold and non-FX products by requiring
   // three-letter ISO-style currency fields from the broker metadata.
   if(base_currency == "XAG" || base_currency == "XPT" ||
      base_currency == "XPD")
      return false;

   market_type = "FOREX";
   return true;
}

string Number(double value, int digits)
{
   return DoubleToString(value, digits);
}

void OnStart()
{
   string server = AccountInfoString(ACCOUNT_SERVER);
   if(StringFind(StringToLower(server), "exness") < 0)
   {
      Print("V9 EXPORT BLOCKED: MT5 server does not identify as Exness.");
      return;
   }

   if(InpAccountType != "Raw Spread")
   {
      Print("V9 EXPORT BLOCKED: configured account type must be Raw Spread.");
      return;
   }

   if(InpCandleCount < 30 || InpCandleCount > 500)
   {
      Print("V9 EXPORT BLOCKED: candle count must be 30..500.");
      return;
   }

   int handle = FileOpen(InpOutputFile,
                         FILE_WRITE|FILE_TXT|FILE_COMMON|FILE_ANSI,
                         0, CP_UTF8);
   if(handle == INVALID_HANDLE)
   {
      Print("V9 EXPORT ERROR: cannot open output file. Error=", GetLastError());
      return;
   }

   FileWriteString(handle, "{\"broker\":\"Exness\",");
   FileWriteString(handle, "\"account_type\":\"Raw Spread\",");
   FileWriteString(handle, "\"platform\":\"MT5\",");
   FileWriteString(handle, "\"mode\":\"READ ONLY\",");
   FileWriteString(handle, "\"server\":\"");
   FileWriteString(handle, server);
   FileWriteString(handle, "\",\"exported_at_utc\":\"");
   FileWriteString(handle, IsoUtc(TimeGMT()));
   FileWriteString(handle, "\",\"snapshots\":[");

   bool first_symbol = true;
   int total = SymbolsTotal(true);
   int exported = 0;

   for(int index = 0; index < total; index++)
   {
      string symbol = SymbolName(index, true);
      string market_type, base_currency, quote_currency;

      if(!IsEligibleSymbol(symbol, market_type, base_currency, quote_currency))
         continue;

      if(!SymbolSelect(symbol, true))
         continue;

      MqlTick tick;
      if(!SymbolInfoTick(symbol, tick) || tick.bid <= 0 || tick.ask < tick.bid)
         continue;

      MqlRates rates[];
      ArraySetAsSeries(rates, false);
      int copied = CopyRates(symbol, PERIOD_M15, 1, InpCandleCount, rates);
      if(copied < 30)
         continue;

      long digits = SymbolInfoInteger(symbol, SYMBOL_DIGITS);
      double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      double tick_size = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
      double tick_value = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
      double contract_size = SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE);
      double volume_min = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
      double volume_max = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
      double volume_step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);

      if(point <= 0 || tick_size <= 0 || tick_value <= 0 ||
         contract_size <= 0 || volume_min <= 0 || volume_max < volume_min ||
         volume_step <= 0)
         continue;

      long trade_mode = SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE);
      bool trade_allowed = (trade_mode != SYMBOL_TRADE_MODE_DISABLED);

      if(!first_symbol)
         FileWriteString(handle, ",");
      first_symbol = false;

      FileWriteString(handle, "{\"symbol\":\"");
      FileWriteString(handle, symbol);
      FileWriteString(handle, "\",\"symbol_metadata\":{");
      FileWriteString(handle, "\"symbol\":\"" + symbol + "\",");
      FileWriteString(handle, "\"market_type\":\"" + market_type + "\",");
      FileWriteString(handle, "\"base_currency\":\"" + base_currency + "\",");
      FileWriteString(handle, "\"quote_currency\":\"" + quote_currency + "\",");
      FileWriteString(handle, "\"digits\":" + IntegerToString((int)digits) + ",");
      FileWriteString(handle, "\"point\":" + Number(point, 10) + ",");
      FileWriteString(handle, "\"tick_size\":" + Number(tick_size, 10) + ",");
      FileWriteString(handle, "\"tick_value\":" + Number(tick_value, 8) + ",");
      FileWriteString(handle, "\"contract_size\":" + Number(contract_size, 4) + ",");
      FileWriteString(handle, "\"volume_min\":" + Number(volume_min, 4) + ",");
      FileWriteString(handle, "\"volume_max\":" + Number(volume_max, 4) + ",");
      FileWriteString(handle, "\"volume_step\":" + Number(volume_step, 4) + ",");
      FileWriteString(handle, "\"trade_allowed\":" + (trade_allowed ? "true" : "false"));
      FileWriteString(handle, "},\"tick\":{");
      FileWriteString(handle, "\"bid\":" + Number(tick.bid, (int)digits) + ",");
      FileWriteString(handle, "\"ask\":" + Number(tick.ask, (int)digits) + ",");
      FileWriteString(handle, "\"timestamp_utc\":\"" + IsoUtc(TimeGMT()) + "\"");
      FileWriteString(handle, "},\"candles\":[");

      for(int candle = 0; candle < copied; candle++)
      {
         if(candle > 0)
            FileWriteString(handle, ",");
         // Broker candle time is converted using the current server/UTC offset.
         // Verify server DST behavior before using this timestamp for research.
         datetime utc_bar = rates[candle].time - (TimeTradeServer() - TimeGMT());
         FileWriteString(handle, "{\"timestamp_utc\":\"" + IsoUtc(utc_bar) + "\",");
         FileWriteString(handle, "\"open\":" + Number(rates[candle].open, (int)digits) + ",");
         FileWriteString(handle, "\"high\":" + Number(rates[candle].high, (int)digits) + ",");
         FileWriteString(handle, "\"low\":" + Number(rates[candle].low, (int)digits) + ",");
         FileWriteString(handle, "\"close\":" + Number(rates[candle].close, (int)digits) + ",");
         FileWriteString(handle, "\"tick_volume\":" + (string)rates[candle].tick_volume + "}");
      }
      FileWriteString(handle, "]}");
      exported++;
   }

   FileWriteString(handle, "]}");
   FileClose(handle);

   Print("V9 READ-ONLY EXPORT COMPLETE. Symbols=", exported,
         " File=Common\\Files\\", InpOutputFile);
   Print("No orders were sent. No positions or account settings were modified.");
}
