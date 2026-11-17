{# Integer date key, e.g. 2026-11-10 -> 20261110. Null stays null. #}
{% macro date_key(date_column) -%}
    (year({{ date_column }}) * 10000 + month({{ date_column }}) * 100 + day({{ date_column }}))
{%- endmacro %}

{# Stable surrogate key: md5 of the listed columns (nulls become empty text). #}
{% macro surrogate_key(columns) -%}
    to_hex(md5(to_utf8(concat_ws('|'
        {%- for c in columns %}, coalesce(cast({{ c }} as varchar), ''){% endfor -%}
    ))))
{%- endmacro %}
