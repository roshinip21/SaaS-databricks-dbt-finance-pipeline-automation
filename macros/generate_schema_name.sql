{#
    Override dbt's default schema naming.

    By DEFAULT, dbt names a model's schema as "<target_schema>_<custom_schema>"
    -- e.g. with target schema `dbt_dev` and a model configured `+schema: marts`,
    the model would land in a schema called `dbt_dev_marts`.

    That prefixing is a safety feature for shared warehouses (so two developers
    don't overwrite each other). For this project we want clean, readable
    schema names -- `staging`, `intermediate`, `marts`, `seed` -- so we use the
    custom schema name as-is when one is set, and fall back to the target's
    schema only when a model has no `+schema` configured.

    Result in Unity Catalog: saas_analytics.marts.fct_invoices, etc.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set default_schema = target.schema -%}
    {%- if custom_schema_name is none -%}
        {{ default_schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
