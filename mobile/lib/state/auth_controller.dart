/// B17 فاز ۳۶ — کنترلر نشست کاربر (Provider/ChangeNotifier).
///
/// - توکن دسترسی در SharedPreferences نگه داشته می‌شود؛ توضیح امنیتی در
///   README: برای تولید از flutter_secure_storage استفاده کنید.
/// - هیچ داده‌ای به‌جز توکن و نمایش نام روی دستگاه ذخیره نمی‌شود؛
///   داده بالینی هرگز کش نمی‌شود (بند حریم خصوصی سند جامع).
library;

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api/api_client.dart';
import '../models/models.dart';

const String _kTokenKey = 'rosepsy.access_token';

class AuthController extends ChangeNotifier {
  AuthController(this._client);

  final ApiClient _client;

  /// دسترسی صفحات به کلاینت REST (توکن همیشه همراه).
  ApiClient get api => _client;

  MyProfile? _profile;
  List<String> _roles = const [];
  bool _restoring = true;

  MyProfile? get profile => _profile;
  List<String> get roles => _roles;
  bool get isAuthed => _profile != null;
  bool get restoring => _restoring;

  bool hasAnyRole(List<String> codes) =>
      roles.any((r) => codes.contains(r));

  /// بازیابی نشست پیشین هنگام شروع اپ.
  Future<void> restore() async {
    _restoring = true;
    try {
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString(_kTokenKey);
      if (token == null) return;
      _client.setToken(token);
      await _loadProfile();
    } on AuthException {
      await _clearToken();
    } on ApiException {
      await _clearToken();
    } catch (_) {
      // خطای شبکه هنگام بازیابی — کاربر وارد می‌شود
      _client.setToken(null);
    } finally {
      _restoring = false;
      notifyListeners();
    }
  }

  Future<void> login(String username, String password) async {
    final data = await _client.post(
      '/auth/login',
      body: {'username': username, 'password': password},
    );
    final token = data['access_token'] as String?;
    if (token == null || token.isEmpty) {
      throw const ApiException(500, 'پاسخ ورود فاقد توکن است');
    }
    _client.setToken(token);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kTokenKey, token);
    await _loadProfile();
    notifyListeners();
  }

  Future<void> logout() async {
    try {
      await _client.post('/auth/logout');
    } catch (_) {
      // خروج سمت سرور best-effort است
    }
    await _clearToken();
    notifyListeners();
  }

  Future<void> refreshProfile() async {
    if (!isAuthed) return;
    await _loadProfile();
    notifyListeners();
  }

  Future<void> _loadProfile() async {
    final data = await _client.get('/me/profile');
    _profile = MyProfile.fromMap(data);
    await _loadRoles();
  }

  /// نقش‌ها از مسیر عمومی کاربر خوانده می‌شود (برای کنترل منو).
  Future<void> _loadRoles() async {
    try {
      final data = await _client.get('/auth/me');
      final rolesRaw = data['roles'];
      _roles = (rolesRaw is List)
          ? rolesRaw.map((e) => e is Map ? '${e['code']}' : '$e').toList()
          : const [];
    } catch (_) {
      _roles = const [];
    }
  }

  Future<void> _clearToken() async {
    _client.setToken(null);
    _profile = null;
    _roles = const [];
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kTokenKey);
  }
}
