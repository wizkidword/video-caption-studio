from src.vcs.analyze import build_frame_sampling_plan


def test_sampling_plan_spreads_indices():
    plan = build_frame_sampling_plan(total_frames=100, max_samples=5)
    assert plan[0] == 0
    assert plan[-1] == 99
    assert len(plan) == 5


def test_sampling_plan_handles_small_inputs():
    assert build_frame_sampling_plan(total_frames=0, max_samples=5) == []
    assert build_frame_sampling_plan(total_frames=3, max_samples=8) == [0, 1, 2]


def test_sampling_plan_handles_single_sample_request():
    assert build_frame_sampling_plan(total_frames=100, max_samples=1) == [0]
