"""
Kinetic Layer 워커 모듈.

Graph Projector와 GWT Consumer를 포함한다.
두 워커 모두 Redis Stream Consumer Group 패턴으로 이벤트를 소비하며,
각각 별도의 Consumer Group을 사용하여 동일 스트림을 독립적으로 처리한다.
"""
