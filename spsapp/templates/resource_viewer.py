{% extends 'base.html' %}

{% block title %}{{ resource.file.name }}{% endblock %}

{% block content %}
<div class="mb-3">
    <a href="{% url 'topicdetails' resource.topic.topic_uuid %}" class="btn btn-secondary">
        <i class="bi bi-arrow-left"></i> Orqaga
    </a>

    <button onclick="openFullscreen()" class="btn btn-success">
        <i class="bi bi-fullscreen"></i> Presentation Mode
    </button>

    <a href="{{ resource.file.url }}" download class="btn btn-primary">
        <i class="bi bi-download"></i> Yuklab olish
    </a>
</div>

<div id="viewer-container" class="border rounded p-2 bg-light">

    {% if resource.pdf_file %}
        <iframe 
            src="{{ resource.pdf_file.url }}" 
            width="100%" 
            height="800" 
            style="border:none;">
        </iframe>

    {% elif resource.file_type == "pdf" %}
        <iframe 
            src="{{ resource.file.url }}" 
            width="100%" 
            height="800" 
            style="border:none;">
        </iframe>

    {% else %}
        <div class="alert alert-warning">
            Bu fayl preview qilinmaydi.
            <br><br>
            <a href="{{ resource.file.url }}" class="btn btn-primary">
                Faylni yuklab olish
            </a>
        </div>
    {% endif %}

</div>
{% endblock %}

{% block scripts %}
<script>
function openFullscreen() {
    const elem = document.getElementById("viewer-container");

    if (elem.requestFullscreen) {
        elem.requestFullscreen();
    } 
    else if (elem.webkitRequestFullscreen) {
        elem.webkitRequestFullscreen();
    } 
    else if (elem.msRequestFullscreen) {
        elem.msRequestFullscreen();
    }
}
</script>
{% endblock %}
