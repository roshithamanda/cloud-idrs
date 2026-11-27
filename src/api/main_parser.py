"""Query parsing for Splunk-style incident search."""

import re

ALLOWED_FIELDS = {'source_ip', 'is_attack', 'risk_level', 'confidence', 'timestamp', 'mitre_technique', 'attack_type'}

def parse_search_query(query: str):
    filters = []
    group_by = None
    sort_field = None
    descending = False
    limit = 100
    parts = [part.strip() for part in query.split('|') if part.strip()]
    if not parts:
        raise ValueError('Query is empty')

    # Security check: disallow SQL keywords in the query DSL
    sql_blacklist = ['UNION', 'SELECT', 'DROP', 'INSERT', 'UPDATE', 'DELETE', '--', ';', '/*', '*/']
    query_upper = query.upper()
    for kw in sql_blacklist:
        if re.search(r'\b' + re.escape(kw) + r'\b', query_upper) or kw in [';', '--', '/*', '*/'] and kw in query:
            raise ValueError(f'Malicious or unsupported SQL syntax detected: {kw}')

    filter_text = parts[0]
    if filter_text.startswith('search '):
        filter_text = filter_text[7:].strip()

    matches = list(re.finditer(r'([a-z_]+)\s*(=|!=|>=|<=|>|<)\s*(?:"([^"]*)"|([^\s]+))', filter_text, re.IGNORECASE))
    
    if not matches and filter_text != '*' and not re.fullmatch(r'source_ip\s*=\s*"\*"', filter_text, re.IGNORECASE):
        raise ValueError('Use supported filters such as source_ip="203.0.113.5" or risk_level="HIGH"')

    for match in matches:
        field, operator, quoted, plain = match.groups()
        value = quoted if quoted is not None else plain
        field = field.lower()
        if field not in ALLOWED_FIELDS:
            raise ValueError(f'Unsupported search field: {field}. Allowed fields: {sorted(ALLOWED_FIELDS)}')
        
        if field == 'is_attack':
            if str(value).lower() in {'true', 'attack', '1'}:
                value = 1
            elif str(value).lower() in {'false', 'normal', '0'}:
                value = 0
            else:
                raise ValueError('is_attack must be true or false')
        elif field == 'confidence':
            try:
                value = float(value)
            except ValueError:
                raise ValueError('confidence must be a valid float')
        elif field == 'source_ip' and value == '*':
            continue
        filters.append((field, operator, value))

    for part in parts[1:]:
        tokens = part.split()
        command = tokens[0].lower()
        if command == 'stats' and len(tokens) == 4 and tokens[1].lower() == 'count' and tokens[2].lower() == 'by':
            group_by = tokens[3].lower()
        elif command == 'sort' and len(tokens) == 2:
            sort_token = tokens[1]
            descending = sort_token.startswith('-')
            sort_field = sort_token.lstrip('-+')
        elif command in {'head', 'limit'} and len(tokens) == 2:
            limit = int(tokens[1])
        else:
            raise ValueError(f'Unsupported query command: {part}')

    return filters, group_by, sort_field, descending, max(1, min(limit, 1000))
