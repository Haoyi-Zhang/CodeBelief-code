int mjson_print_dbl(mjson_print_fn_t fn, void *fnd, double d, int width) {
  char buf[40];
  int i, s = 0, n = 0, e = 0;
  double t, mul, saved;
  if (d == 0.0) return fn("0", 1, fnd);
  if (isinf(d)) return fn(d > 0 ? "inf" : "-inf", d > 0 ? 3 : 4, fnd);
  if (isnan(d)) return fn("nan", 3, fnd);
  if (d < 0.0) d = -d, buf[s++] = '-';

  // Round
  saved = d;
  mul = 1.0;
  while (d >= 10.0 && d / mul >= 10.0) mul *= 10.0;
  while (d <= 1.0 && d / mul <= 1.0) mul /= 10.0;
  for (i = 0, t = mul * 5; i < width; i++) t /= 10.0;
  d += t;
  // Calculate exponent, and 'mul' for scientific representation
  mul = 1.0;
  while (d >= 10.0 && d / mul >= 10.0) mul *= 10.0, e++;
  while (d < 1.0 && d / mul < 1.0) mul /= 10.0, e--;
  // printf(" --> %g %d %g %g\n", saved, e, t, mul);

  if (e >= width) {
    struct mjson_fixedbuf fb = {buf + s, (int) sizeof(buf) - s, 0};
    n = mjson_print_dbl(mjson_print_fixed_buf, &fb, saved / mul, width);
    // printf(" --> %.*g %d [%.*s]\n", 10, d / t, e, fb.len, fb.ptr);
    n += addexp(buf + s + n, e, '+');
    return fn(buf, s + n, fnd);
  } else if (e <= -width) {
    struct mjson_fixedbuf fb = {buf + s, (int) sizeof(buf) - s, 0};
    n = mjson_print_dbl(mjson_print_fixed_buf, &fb, saved / mul, width);
    // printf(" --> %.*g %d [%.*s]\n", 10, d / mul, e, fb.len, fb.ptr);
    n += addexp(buf + s + n, -e, '-');
    return fn(buf, s + n, fnd);
  } else {
    for (i = 0, t = mul; d >= 1.0 && s + n < (int) sizeof(buf); i++) {
      int ch = (int) (d / t);
      if (n > 0 || ch > 0) buf[s + n++] = (char) (ch + '0');
      d -= ch * t;
      t /= 10.0;
    }
    // printf(" --> [%g] -> %g %g (%d) [%.*s]\n", saved, d, t, n, s + n, buf);
    if (n == 0) buf[s++] = '0';
    while (t >= 1.0 && n + s < (int) sizeof(buf)) buf[n++] = '0', t /= 10.0;
    if (s + n < (int) sizeof(buf)) buf[n + s++] = '.';
    // printf(" 1--> [%g] -> [%.*s]\n", saved, s + n, buf);
    for (i = 0, t = 0.1; s + n < (int) sizeof(buf) && n < width; i++) {
      int ch = (int) (d / t);
      buf[s + n++] = (char) (ch + '0');
      d -= ch * t;
      t /= 10.0;
    }
  }
  while (n > 0 && buf[s + n - 1] == '0') n--;  // Trim trailing zeros
  if (n > 0 && buf[s + n - 1] == '.') n--;     // Trim trailing dot
  return fn(buf, s + n, fnd);
}
