{# Trim a text column, collapse repeated spaces, and turn placeholder text (N/A, null, None, blank)
   into a real null. Mirrors the text cleaning in the exploration notebook (section 5.1). #}
{% macro clean_text(column) -%}
    case
        when upper(trim(regexp_replace({{ column }}, '\s+', ' '))) in ('N/A', 'NULL', 'NONE', '') then null
        else trim(regexp_replace({{ column }}, '\s+', ' '))
    end
{%- endmacro %}
