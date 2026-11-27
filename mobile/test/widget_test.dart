import 'package:flutter_test/flutter_test.dart';
import 'package:v9_odysseus_app/main.dart';

void main() {
  testWidgets('shows setup-required state when Supabase config is absent',
      (tester) async {
    await tester.pumpWidget(const V9OdysseusApp());

    expect(find.text('Konfigurasi diperlukan'), findsOneWidget);
    expect(find.text('V9 ODYSSEUS'), findsOneWidget);
  });

  testWidgets('market intelligence shows an honest empty state', (tester) async {
    await tester.pumpWidget(const MaterialAppForTest(child: MarketEmptyState()));

    expect(find.text('Belum ada sinyal pasar'), findsOneWidget);
    expect(find.textContaining('belum menerima atau menghasilkan data market'),
        findsOneWidget);
  });

  testWidgets('risk monitoring shows an honest empty state', (tester) async {
    await tester.pumpWidget(const MaterialAppForTest(child: RiskEmptyState()));

    expect(find.text('Belum ada penilaian risiko'), findsOneWidget);
    expect(find.textContaining('Tidak ada risiko transaksi'), findsOneWidget);
  });
}

class MaterialAppForTest extends StatelessWidget {
  const MaterialAppForTest({required this.child, super.key});
  final Widget child;

  @override
  Widget build(BuildContext context) => MaterialApp(home: Scaffold(body: child));
}
