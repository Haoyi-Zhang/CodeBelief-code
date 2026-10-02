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
    touch();
}

void case_03(void) {
    touch();
}

void case_04(void) {
    lock();
    touch();
    unlock();
    touch();
}

void case_05(void) {
    lock();
    touch();
    unlock();
    touch();
}
