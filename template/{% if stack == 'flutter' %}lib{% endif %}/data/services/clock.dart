/// The current time, behind an interface so tests can stop it (TST-4).
abstract interface class Clock {
  /// Returns the current local time.
  DateTime now();
}

/// The real clock.
class SystemClock implements Clock {
  @override
  DateTime now() => DateTime.now();
}
