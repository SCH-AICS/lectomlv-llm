from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('llm', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='llmquery',
            name='video_clips',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='인용된 영상 구간의 ffmpeg 클립 생성 결과',
            ),
        ),
    ]
