#!/usr/bin/env python

from faq_annotation.crew import FaqAnnotation


def run():
    inputs = {"batch_data": "id|inflo_chnl_id|reg_dts|질문|답변|액션|버튼|intent_id\n"}
    FaqAnnotation().crew().kickoff(inputs=inputs)


def train():
    raise RuntimeError("실제 실행 진입점은 프로젝트 루트의 run_annotation.py 입니다.")


def replay():
    raise RuntimeError("실제 실행 진입점은 프로젝트 루트의 run_annotation.py 입니다.")


def test():
    raise RuntimeError("실제 실행 진입점은 프로젝트 루트의 run_annotation.py 입니다.")


def run_with_trigger():
    raise RuntimeError("실제 실행 진입점은 프로젝트 루트의 run_annotation.py 입니다.")
