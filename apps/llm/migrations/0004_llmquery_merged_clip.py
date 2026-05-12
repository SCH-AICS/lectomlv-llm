from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('llm', '0003_llmquery_video_clips'),
    ]

    operations = [
        migrations.AddField(
            model_name='llmquery',
            name='merged_clip',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='클립 머지 결과 (merged_filename, merged_url, status)',
            ),
        ),
    ]
