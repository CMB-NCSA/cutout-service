{% for file in file_info %}
mkdir -p $(dirname "./{{ job_id }}/{{ file.path }}")
wget --output-document "./{{ job_id }}/{{ file.path }}" \
    "{{ file.url }}"
{% endfor %}
echo "Job files downloaded."
