/* Original benign static fixture. Symbolic calls; not a production program. */
void lock(void);
void unlock(void);
void touch(void);
void noop(void);

void alpha(void) {
    lock();
    touch();
    unlock();
}

void beta(void) {
    touch();
}

void gamma(void) {
    lock();
    touch();
    unlock();
    touch();
}
