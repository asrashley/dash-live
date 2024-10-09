export const routeMap = {
{%- for name, route in routes.items() %}
  "{{ name }}": {
    "title": "{{ route.title }}",
    "template": "{{ route.template }}",
    "re": /{{ route.re | safe }}/,
  },
{%- endfor %}
};
