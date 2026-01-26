// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility that Flutter provides. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter_test/flutter_test.dart';

import 'package:mumble_ai_flutter/main.dart';
import 'package:mumble_ai_flutter/services/storage_service.dart';
import 'package:mumble_ai_flutter/services/api_service.dart';
import 'package:mumble_ai_flutter/services/audio_service.dart';

void main() {
  testWidgets('App loads without crashing', (WidgetTester tester) async {
    // Create mock services
    final storageService = await StorageService.getInstance();
    final apiService = ApiService.getInstance();
    final audioService = AudioService.getInstance();

    // Build our app and trigger a frame.
    await tester.pumpWidget(MyApp(
      storageService: storageService,
      apiService: apiService,
      audioService: audioService,
    ));

    // Verify that the server connect screen is shown
    expect(find.text('Mumble AI Control Panel'), findsOneWidget);
    expect(find.text('Connect to your Mumble AI server'), findsOneWidget);
  });
}