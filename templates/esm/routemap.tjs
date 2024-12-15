export const routeMap = {
{%- for name, route in routes.items() %}
  {{ name }}: {
    title: "{{ route.title }}",
    re: /{{ route.re | safe }}/,
    route: "{{ route.route }}",
    url: {{ route.url | safe }},
  },
{%- endfor %}
};

