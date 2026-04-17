from django.core.management.base import BaseCommand

from apps.lectures.models import Lecture
from apps.lectures.tasks import index_lecture_segments


class Command(BaseCommand):
    help = "인덱싱되지 않은 강의를 FAISS 벡터 인덱스에 등록합니다"

    def add_arguments(self, parser):
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Celery 대신 동기적으로 실행",
        )

    def handle(self, *args, **options):
        lectures = Lecture.objects.filter(is_indexed=False)
        if not lectures.exists():
            self.stdout.write("인덱싱할 강의가 없습니다.")
            return

        for lecture in lectures:
            self.stdout.write(f"인덱싱 중: {lecture.title} ...")
            if options["sync"]:
                result = index_lecture_segments(lecture.id)
                self.stdout.write(self.style.SUCCESS(f"  완료: {result}"))
            else:
                task = index_lecture_segments.delay(lecture.id)
                self.stdout.write(f"  Celery 태스크 전송: {task.id}")

        self.stdout.write(
            self.style.SUCCESS(f"\n{lectures.count()}개 강의 인덱싱 {'완료' if options['sync'] else '요청 완료'}")
        )
