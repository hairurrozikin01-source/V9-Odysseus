import unittest

from portfolio_risk_gate import evaluate_portfolio_risk


class PortfolioRiskGateTests(unittest.TestCase):
    def setUp(self):
        self.account = {"equity": 10000, "daily_loss_amount": 100}
        self.positions = [
            {
                "position_id": "demo-1",
                "risk_amount": 50,
                "currency_exposure": {"USD": 100, "EUR": 50},
            },
            {
                "position_id": "demo-2",
                "risk_amount": 40,
                "currency_exposure": {"USD": 80, "JPY": 40},
            },
        ]

    def test_values_within_limits_do_not_authorize_new_risk(self):
        result = evaluate_portfolio_risk(self.account, self.positions)
        self.assertEqual(result["status"], "WITHIN_LIMITS")
        self.assertFalse(result["safety"]["new_risk_allowed"])
        self.assertFalse(result["safety"]["orders_enabled"])

    def test_daily_loss_limit_blocks(self):
        account = dict(self.account, daily_loss_amount=300)
        result = evaluate_portfolio_risk(account, self.positions)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("DAILY_LOSS_LIMIT_REACHED", [x["code"] for x in result["flags"]])

    def test_per_position_risk_limit_blocks(self):
        positions = [dict(self.positions[0], risk_amount=150)]
        result = evaluate_portfolio_risk(self.account, positions)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("POSITION_RISK_LIMIT_EXCEEDED", [x["code"] for x in result["flags"]])

    def test_combined_open_risk_limit_blocks(self):
        positions = [
            dict(self.positions[0], risk_amount=300),
            dict(self.positions[1], risk_amount=250),
        ]
        result = evaluate_portfolio_risk(self.account, positions)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("TOTAL_OPEN_RISK_LIMIT_REACHED", [x["code"] for x in result["flags"]])

    def test_currency_concentration_blocks(self):
        positions = [
            {"position_id": "demo-1", "risk_amount": 10,
             "currency_exposure": {"USD": 300}}
        ]
        result = evaluate_portfolio_risk(self.account, positions)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(
            "CURRENCY_CONCENTRATION_LIMIT_REACHED",
            [x["code"] for x in result["flags"]],
        )

    def test_duplicate_position_ids_rejected(self):
        positions = [self.positions[0], dict(self.positions[0])]
        with self.assertRaises(ValueError):
            evaluate_portfolio_risk(self.account, positions)

    def test_missing_currency_exposure_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_portfolio_risk(
                self.account,
                [{"position_id": "x", "risk_amount": 10}],
            )

    def test_invalid_equity_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_portfolio_risk({"equity": 0, "daily_loss_amount": 0}, [])

    def test_invalid_numbers_rejected(self):
        account = dict(self.account, daily_loss_amount=float("nan"))
        with self.assertRaises(ValueError):
            evaluate_portfolio_risk(account, [])


if __name__ == "__main__":
    unittest.main()
