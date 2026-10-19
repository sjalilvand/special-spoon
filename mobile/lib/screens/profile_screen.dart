/// B17 فاز ۳۶ — تب پروفایل من (/me/profile).
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/auth_controller.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key, required this.onError});

  final void Function(Object error) onError;

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthController>();
    final profile = auth.profile;
    if (profile == null) {
      return const Center(child: CircularProgressIndicator());
    }
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    CircleAvatar(
                      child: Text(profile.displayName.isNotEmpty
                          ? profile.displayName.characters.first
                          : '؟'),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        profile.displayName,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ),
                  ],
                ),
                const Divider(height: 24),
                _row('کد ملی', profile.nationalId),
                _row('موبایل', profile.mobile),
                _row('واحد', profile.unitTitle),
              ],
            ),
          ),
        ),
        const SizedBox(height: 8),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('نقش‌های من', style: Theme.of(context).textTheme.titleSmall),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  children: [
                    for (final r in auth.roles) Chip(label: Text(r)),
                  ],
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 8),
        Card(
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
          child: const Padding(
            padding: EdgeInsets.all(16),
            child: Text(
              'یادآوری حریم خصوصی: داده‌های حساس شما فقط در حافظه نشست جاری '
              'نمایش داده می‌شود و روی دستگاه ذخیره/کش نمی‌شود.',
              style: TextStyle(fontSize: 12),
            ),
          ),
        ),
      ],
    );
  }

  Widget _row(String label, String? value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 80,
            child: Text(label,
                style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
          ),
          Expanded(child: Text(value ?? '—', style: const TextStyle(fontSize: 13))),
        ],
      ),
    );
  }
}
