import 'dart:typed_data';
import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';

class AudioService {
  static AudioService? _instance;
  late AudioPlayer _audioPlayer;
  bool _isPlaying = false;

  AudioService._() {
    _audioPlayer = AudioPlayer();
    _audioPlayer.onPlayerStateChanged.listen((PlayerState state) {
      _isPlaying = state == PlayerState.playing;
    });
  }

  static AudioService getInstance() {
    _instance ??= AudioService._();
    return _instance!;
  }

  bool get isPlaying => _isPlaying;

  // Play audio from URL
  Future<void> playFromUrl(String url) async {
    try {
      await _audioPlayer.stop(); // Stop any currently playing audio
      await _audioPlayer.play(UrlSource(url));
    } catch (e) {
      if (kDebugMode) {
        print('Error playing audio: $e');
      }
      throw Exception('Failed to play audio: $e');
    }
  }

  // Play audio from bytes (for API responses)
  Future<void> playFromBytes(List<int> bytes) async {
    try {
      await _audioPlayer.stop(); // Stop any currently playing audio
      await _audioPlayer.play(BytesSource(Uint8List.fromList(bytes)));
    } catch (e) {
      if (kDebugMode) {
        print('Error playing audio from bytes: $e');
      }
      throw Exception('Failed to play audio: $e');
    }
  }

  // Pause audio
  Future<void> pause() async {
    try {
      await _audioPlayer.pause();
    } catch (e) {
      if (kDebugMode) {
        print('Error pausing audio: $e');
      }
    }
  }

  // Resume audio
  Future<void> resume() async {
    try {
      await _audioPlayer.resume();
    } catch (e) {
      if (kDebugMode) {
        print('Error resuming audio: $e');
      }
    }
  }

  // Stop audio
  Future<void> stop() async {
    try {
      await _audioPlayer.stop();
    } catch (e) {
      if (kDebugMode) {
        print('Error stopping audio: $e');
      }
    }
  }

  // Set volume (0.0 to 1.0)
  Future<void> setVolume(double volume) async {
    try {
      await _audioPlayer.setVolume(volume.clamp(0.0, 1.0));
    } catch (e) {
      if (kDebugMode) {
        print('Error setting volume: $e');
      }
    }
  }

  // Dispose resources
  void dispose() {
    _audioPlayer.dispose();
  }
}
