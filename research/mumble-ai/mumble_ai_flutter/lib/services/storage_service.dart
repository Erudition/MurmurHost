import 'package:shared_preferences/shared_preferences.dart';

class StorageService {
  static const String _serverUrlKey = 'server_url';
  static const String _rememberServerKey = 'remember_server';
  static const String _selectedUserKey = 'selected_user';

  static StorageService? _instance;
  static SharedPreferences? _prefs;

  StorageService._();

  static Future<StorageService> getInstance() async {
    _instance ??= StorageService._();
    _prefs ??= await SharedPreferences.getInstance();
    return _instance!;
  }

  // Server URL management
  Future<String?> getServerUrl() async {
    return _prefs?.getString(_serverUrlKey);
  }

  Future<bool> setServerUrl(String url) async {
    return await _prefs?.setString(_serverUrlKey, url) ?? false;
  }

  Future<bool> removeServerUrl() async {
    return await _prefs?.remove(_serverUrlKey) ?? false;
  }

  // Remember server preference
  Future<bool> getRememberServer() async {
    return _prefs?.getBool(_rememberServerKey) ?? true;
  }

  Future<bool> setRememberServer(bool remember) async {
    return await _prefs?.setBool(_rememberServerKey, remember) ?? false;
  }

  // Selected user management
  Future<String?> getSelectedUser() async {
    return _prefs?.getString(_selectedUserKey);
  }

  Future<bool> setSelectedUser(String user) async {
    return await _prefs?.setString(_selectedUserKey, user) ?? false;
  }

  Future<bool> removeSelectedUser() async {
    return await _prefs?.remove(_selectedUserKey) ?? false;
  }

  // Clear all data
  Future<bool> clearAll() async {
    return await _prefs?.clear() ?? false;
  }
}
