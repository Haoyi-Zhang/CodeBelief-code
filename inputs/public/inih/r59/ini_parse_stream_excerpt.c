int ini_parse_stream(ini_reader reader, void* stream, ini_handler handler,
                     void* user)
{
    /* Uses a fair bit of stack (use heap instead if you need to) */
#if INI_USE_STACK
    char line[INI_MAX_LINE];
    size_t max_line = INI_MAX_LINE;
#else
    char* line;
    size_t max_line = INI_INITIAL_ALLOC;
#endif
#if INI_ALLOW_REALLOC && !INI_USE_STACK
    char* new_line;
#endif
    char section[MAX_SECTION] = "";
#if INI_ALLOW_MULTILINE
    char prev_name[MAX_NAME] = "";
#endif

    size_t offset;
    char* start;
    char* end;
    char* name;
    char* value;
    int lineno = 0;
    int error = 0;
    char abyss[16];  /* Used to consume input when a line is too long. */

    /* Scan through stream line by line */
    while (reader(line, (int)max_line, stream) != NULL) {
        offset = strlen(line);

#if INI_ALLOW_REALLOC && !INI_USE_STACK
        while (offset == max_line - 1 && line[offset - 1] != '\n') {
            max_line *= 2;
            if (max_line > INI_MAX_LINE)
                max_line = INI_MAX_LINE;
            new_line = ini_realloc(line, max_line);
            if (!new_line) {
                ini_free(line);
                return -2;
            }
            line = new_line;
            if (reader(line + offset, (int)(max_line - offset), stream) == NULL)
                break;
            offset += strlen(line + offset);
            if (max_line >= INI_MAX_LINE)
                break;
        }
#endif

        lineno++;

        /* If line exceeded INI_MAX_LINE bytes, discard till end of line. */
        if (offset == max_line - 1 && line[offset - 1] != '\n') {
            while (reader(abyss, sizeof(abyss), stream) != NULL) {
                if (!error)
                    error = lineno;
                if (abyss[strlen(abyss) - 1] == '\n')
                    break;
            }
        }
