from django.core.management.base import BaseCommand

from apps.lectures.models import Lecture, LectureSegment


SEED_DATA = [
    {
        "title": "인공지능과 기계학습 1강 - 개론",
        "source_file": "p1 1. 인공지능과 기계학습 (Revised).pdf",
        "description": "인공지능, 머신러닝, 딥러닝 기본 개념 소개",
        "segments": [
            {
                "start_time": "00:01",
                "end_time": "01:36",
                "transcript": (
                    "오늘 수업은 저번 시간에 했던 거 마저 요 일장 좀 얘기를 하고 "
                    "그 다음에 예관대로 간단한 퀴즈를 보고 그 다음에 챕터 1 수업을 진행을 하도록 하죠. "
                    "저번 시간에 얘기했던 거는 인공지능이라는 거와 머실러닝이라는 거가 뭔가 라는 거 "
                    "그리고 어떤 문제들이 있는가 라는 것들에 대한 이 얘기를 했었죠. "
                    "그러니까 다시 한번 얘기하지"
                ),
            },
            {
                "start_time": "01:37",
                "end_time": "04:22",
                "transcript": (
                    "인공지능이라는 거는 기계가 지능적인 행동을 하는 것을 말합니다. "
                    "머신러닝은 데이터로부터 학습을 해서 예측이나 판단을 내리는 거죠. "
                    "딥러닝은 머신러닝의 한 종류로 신경망을 깊게 쌓아서 복잡한 패턴을 학습하는 방법입니다. "
                    "그래서 인공지능이 가장 큰 범주이고 그 안에 머신러닝이 있고 "
                    "머신러닝 안에 딥러닝이 포함되는 구조입니다."
                ),
            },
            {
                "start_time": "04:23",
                "end_time": "08:15",
                "transcript": (
                    "머신러닝의 종류를 보면 크게 지도학습 비지도학습 강화학습 이렇게 세 가지로 나눌 수 있습니다. "
                    "지도학습은 정답이 있는 데이터를 가지고 학습하는 거고 "
                    "비지도학습은 정답 없이 데이터의 구조를 파악하는 거죠. "
                    "강화학습은 에이전트가 환경과 상호작용하면서 보상을 최대화하는 방향으로 학습합니다."
                ),
            },
            {
                "start_time": "08:16",
                "end_time": "12:40",
                "transcript": (
                    "지도학습의 대표적인 예시로는 분류와 회귀가 있습니다. "
                    "분류는 이메일이 스팸인지 아닌지 구분하는 것처럼 카테고리를 예측하는 거고 "
                    "회귀는 집값이나 주가처럼 연속적인 값을 예측하는 겁니다. "
                    "이 두 가지가 지도학습에서 가장 기본적인 문제 유형이에요."
                ),
            },
            {
                "start_time": "12:41",
                "end_time": "17:30",
                "transcript": (
                    "비지도학습의 예시로는 클러스터링이 있어요. "
                    "예를 들어 고객 데이터를 가지고 비슷한 고객끼리 그룹을 묶는 거죠. "
                    "k-means 알고리즘이 대표적인 클러스터링 방법입니다. "
                    "또 차원 축소라는 것도 비지도학습의 한 종류인데 PCA가 대표적입니다."
                ),
            },
        ],
    },
    {
        "title": "인공지능과 기계학습 2강 - 선형 회귀",
        "source_file": "p2 2. 선형 회귀 (Revised).pdf",
        "description": "선형 회귀 모델의 원리와 경사하강법",
        "segments": [
            {
                "start_time": "00:00",
                "end_time": "03:45",
                "transcript": (
                    "오늘은 선형 회귀에 대해서 배워보겠습니다. "
                    "선형 회귀는 가장 기본적인 머신러닝 모델이에요. "
                    "입력 변수 x와 출력 변수 y 사이의 선형 관계를 찾는 겁니다. "
                    "y equals w times x plus b 이런 형태의 직선을 데이터에 맞추는 거죠."
                ),
            },
            {
                "start_time": "03:46",
                "end_time": "08:20",
                "transcript": (
                    "그러면 어떻게 가장 좋은 직선을 찾을까요? "
                    "손실 함수라는 것을 정의합니다. MSE 즉 평균 제곱 오차를 많이 씁니다. "
                    "예측값과 실제값의 차이를 제곱해서 평균을 내는 거예요. "
                    "이 손실 함수를 최소화하는 w와 b를 찾는 것이 학습의 목표입니다."
                ),
            },
            {
                "start_time": "08:21",
                "end_time": "14:10",
                "transcript": (
                    "손실 함수를 최소화하기 위해 경사하강법을 사용합니다. "
                    "경사하강법은 현재 위치에서 기울기의 반대 방향으로 조금씩 이동하는 방법이에요. "
                    "학습률이라는 하이퍼파라미터가 있는데 이것이 한 번에 얼마나 이동할지를 결정합니다. "
                    "학습률이 너무 크면 발산하고 너무 작으면 학습이 느려집니다."
                ),
            },
            {
                "start_time": "14:11",
                "end_time": "19:00",
                "transcript": (
                    "다중 선형 회귀는 입력 변수가 여러 개인 경우입니다. "
                    "예를 들어 집값을 예측할 때 면적뿐만 아니라 방 개수 층수 역세권 여부 등 "
                    "여러 변수를 동시에 고려하는 거죠. "
                    "이때는 w가 벡터가 되고 행렬 연산으로 계산합니다."
                ),
            },
        ],
    },
    {
        "title": "인공지능과 기계학습 3강 - 분류",
        "source_file": "p3 3. 분류 (Revised).pdf",
        "description": "로지스틱 회귀와 분류 알고리즘",
        "segments": [
            {
                "start_time": "00:00",
                "end_time": "04:30",
                "transcript": (
                    "오늘은 분류 문제에 대해서 알아보겠습니다. "
                    "회귀가 연속적인 값을 예측한다면 분류는 카테고리를 예측하는 거예요. "
                    "이진 분류는 두 개의 클래스 중 하나를 선택하는 문제이고 "
                    "다중 분류는 세 개 이상의 클래스 중 하나를 선택하는 문제입니다."
                ),
            },
            {
                "start_time": "04:31",
                "end_time": "09:15",
                "transcript": (
                    "로지스틱 회귀는 이름은 회귀이지만 사실 분류 모델입니다. "
                    "시그모이드 함수를 사용해서 출력을 0과 1 사이의 확률로 변환하는 거예요. "
                    "0.5보다 크면 클래스 1 작으면 클래스 0으로 분류합니다. "
                    "손실 함수로는 크로스 엔트로피를 사용합니다."
                ),
            },
            {
                "start_time": "09:16",
                "end_time": "15:00",
                "transcript": (
                    "결정 트리는 스무고개처럼 질문을 해서 데이터를 분류하는 모델입니다. "
                    "각 노드에서 하나의 특성에 대한 질문을 하고 그 답에 따라 가지를 나눕니다. "
                    "장점은 해석이 쉽다는 거고 단점은 과적합이 쉽게 일어난다는 겁니다. "
                    "이것을 개선한 것이 랜덤 포레스트와 그래디언트 부스팅입니다."
                ),
            },
        ],
    },
]


class Command(BaseCommand):
    help = "더미 강의 데이터를 생성합니다"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="기존 데이터를 삭제하고 새로 생성",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            count = Lecture.objects.count()
            Lecture.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"기존 강의 {count}개 삭제"))

        created_count = 0
        for lecture_data in SEED_DATA:
            lecture, created = Lecture.objects.get_or_create(
                title=lecture_data["title"],
                defaults={
                    "source_file": lecture_data["source_file"],
                    "description": lecture_data["description"],
                },
            )
            if not created:
                self.stdout.write(f"  이미 존재: {lecture.title}")
                continue

            segments = [
                LectureSegment(
                    lecture=lecture,
                    start_time=seg["start_time"],
                    end_time=seg["end_time"],
                    transcript=seg["transcript"],
                )
                for seg in lecture_data["segments"]
            ]
            LectureSegment.objects.bulk_create(segments)
            created_count += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"  생성: {lecture.title} ({len(segments)}개 구간)"
                )
            )

        self.stdout.write(self.style.SUCCESS(f"\n총 {created_count}개 강의 생성 완료"))
        self.stdout.write(
            self.style.WARNING(
                "벡터 인덱싱을 하려면: python manage.py index_lectures"
            )
        )
