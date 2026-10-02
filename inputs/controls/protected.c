/* Original benign static fixture. Symbolic calls; not a production program. */
void lock(void);
void unlock(void);
void touch(void);
void noop(void);

void case_00(void) {
    lock();
    touch();
    unlock();
}

void case_01(void) {
    lock();
    touch();
    unlock();
}

void case_02(void) {
    lock();
    touch();
    unlock();
}
