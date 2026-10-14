// expect: public_member_api_docs, avoid_positional_boolean_parameters, avoid_print, no_default_cases, avoid_dynamic_calls
enum Size { small, large }

void report(String name, bool loud) {
  print(loud ? name.toUpperCase() : name);
}

/// Describes a size.
String describe(Size size) {
  switch (size) {
    case Size.small:
      return 'small';
    default:
      return 'other';
  }
}

/// Reads a field nobody declared.
Object? read(dynamic value) => value.field;
