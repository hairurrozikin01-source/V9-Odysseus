import unittest

from risk_calculator import calculate_position_risk, RiskCalculationError


def metadata(**overrides):
    data = {
        "symbol": "XAUUSD",
        "source": "MT5",
        "mode": "READ ONLY",
        "tick_size": 0.01,
        "tick_value": 1.0,
        "tick_value_currency": "USD",
        "volume_min": 0.01,
        "volume_max": 100.0,
        "volume_step": 0.01,
    }
    data.update(overrides)
    return data


class RiskCalculatorTests(unittest.TestCase):
    def test_calculates_volume_and_floors_to_step(self):
        result = calculate_position_risk(
            symbol_metadata=metadata(),
            side="BUY",
            entry_price=2000.0,
            stop_loss_price=1999.0,
            equity=1000.0,
            risk_pct=1.0,
            account_currency="USD",
        )
        self.assertEqual(result["status"], "CALCULATED")
        self.assertEqual(result["volume_lots"], 0.1)
        self.assertLessEqual(
            result["estimated_stop_risk_account_currency"],
            result["risk_budget_account_currency"],
        )
        self.assertFalse(result["orders_enabled"])

    def test_sell_stop_must_be_above_entry(self):
        with self.assertRaises(RiskCalculationError):
            calculate_position_risk(
                symbol_metadata=metadata(),
                side="SELL",
                entry_price=2000,
                stop_loss_price=1999,
                equity=1000,
                risk_pct=1,
                account_currency="USD",
            )

    def test_buy_stop_must_be_below_entry(self):
        with self.assertRaises(RiskCalculationError):
            calculate_position_risk(
                symbol_metadata=metadata(),
                side="BUY",
                entry_price=2000,
                stop_loss_price=2001,
                equity=1000,
                risk_pct=1,
            )

    def test_below_minimum_volume_blocks(self):
        result = calculate_position_risk(
            symbol_metadata=metadata(),
            side="BUY",
            entry_price=2000,
            stop_loss_price=1900,
            equity=100,
            risk_pct=0.1,
            account_currency="USD",
        )
        self.assertEqual(result["status"], "BLOCKED_BELOW_MIN_VOLUME")
        self.assertEqual(result["volume_lots"], 0.0)

    def test_volume_is_capped_at_broker_max(self):
        result = calculate_position_risk(
            symbol_metadata=metadata(volume_max=0.05),
            side="BUY",
            entry_price=2000,
            stop_loss_price=1999,
            equity=100000,
            risk_pct=1,
        )
        self.assertEqual(result["status"], "CAPPED_AT_BROKER_MAX")
        self.assertEqual(result["volume_lots"], 0.05)

    def test_commission_and_slippage_reduce_volume(self):
        baseline = calculate_position_risk(
            symbol_metadata=metadata(),
            side="BUY",
            entry_price=2000,
            stop_loss_price=1999,
            equity=1000,
            risk_pct=1,
        )
        charged = calculate_position_risk(
            symbol_metadata=metadata(),
            side="BUY",
            entry_price=2000,
            stop_loss_price=1999,
            equity=1000,
            risk_pct=1,
            commission_per_lot_round_turn=2.0,
            slippage_ticks_per_lot=3.0,
        )
        self.assertLessEqual(charged["volume_lots"], baseline["volume_lots"])

    def test_missing_tick_value_fails_closed(self):
        data = metadata()
        del data["tick_value"]
        with self.assertRaises(RiskCalculationError):
            calculate_position_risk(
                symbol_metadata=data,
                side="BUY",
                entry_price=2000,
                stop_loss_price=1999,
                equity=1000,
                risk_pct=1,
            )

    def test_wrong_metadata_source_rejected(self):
        with self.assertRaises(RiskCalculationError):
            calculate_position_risk(
                symbol_metadata=metadata(source="MANUAL"),
                side="BUY",
                entry_price=2000,
                stop_loss_price=1999,
                equity=1000,
                risk_pct=1,
            )

    def test_risk_percentage_over_100_rejected(self):
        with self.assertRaises(RiskCalculationError):
            calculate_position_risk(
                symbol_metadata=metadata(),
                side="BUY",
                entry_price=2000,
                stop_loss_price=1999,
                equity=1000,
                risk_pct=101,
            )

    def test_tick_value_currency_must_match_account(self):
        with self.assertRaises(RiskCalculationError):
            calculate_position_risk(
                symbol_metadata=metadata(tick_value_currency="USD"),
                side="BUY",
                entry_price=2000,
                stop_loss_price=1999,
                equity=1000,
                risk_pct=1,
                account_currency="IDR",
            )

    def test_orders_always_disabled(self):
        result = calculate_position_risk(
            symbol_metadata=metadata(),
            side="SELL",
            entry_price=2000,
            stop_loss_price=2001,
            equity=1000,
            risk_pct=1,
        )
        self.assertEqual(result["mode"], "READ ONLY")
        self.assertFalse(result["orders_enabled"])
        self.assertFalse(result["automated_trade_instruction"])


if __name__ == "__main__":
    unittest.main()
