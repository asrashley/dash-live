{% extends 'layout.html' %}


{% block content %}
<div id="user-management" class="container">
  <h1>User Accounts</h1>
  <div class="users-list-wrap">
  <table class="table table-striped table-bordered users-list" data-csrf="{{csrf_token}}">
    <caption>Users</caption>
    <thead>
      <tr>
	<th class="pk" scope="col">#</th>
	<th class="username" scope="col">Username</th>
	<th class="email" scope="col">Email</th>
	<th class="last-login" scope="col">Last Login</th>
	<th class="must-change bool-col" scope="col">Must Change Password</th>
	{% for name in group_names %}
	<th class="{name}-group bool-col" scope="col">{{ name | title }}</th>
	{% endfor %}
      </tr>
    </thead>
    <tbody>
    {% for user in users %}
    <tr>
      <th class="pk" scope="row">{{ user.pk }}</th>
      <td class="username">
	<a href="{{ url_for('edit-user', upk=user.pk) }}">{{ user.username }}</a>
      </td>
      <td class="email">
	<a href="{{ url_for('edit-user', upk=user.pk) }}">{{ user.email }}</a>
      </td>
      <td class="last-login">{{ user.last_login | dateTimeFormat("%H:%M:%S %d/%m/%Y") }}</td>
      <td class="must-change bool-col">{{ user.must_change | toHtmlString }}</td>
      {% for name in group_names %}
      <td class="{name}-group bool-col">{{ user['groups'][name] | toHtmlString }}</td>
      {% endfor %}
    </tr>
    {% endfor %}
  </tbody>
  </table>
  <a href="{{ url_for('add-user') }}" class="btn btn-success add-user">Add</a>
</div>
</div>
{% endblock %}

