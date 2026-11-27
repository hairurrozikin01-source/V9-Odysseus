import 'package:flutter_test/flutter_test.dart';
import 'package:v9_odysseus_app/main.dart';

void main() {
  testWidgets('shows setup-required state when Supabase config is absent',
      (tester) async {
    await tester.pumpWidget(const V9OdysseusApp());

    expect(find.text('Konfigurasi diperlukan'), findsOneWidget);
    expect(find.text('V9 ODYSSEUS'), findsOneWidget);
  });
}
