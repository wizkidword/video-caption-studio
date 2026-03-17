from src.vcs.analyze import AnalysisResult
from src.vcs.compose import ComposeRequest, compose_content
from src.vcs.ingest import VideoMetadata


def test_local_provider_contract_outputs_nonempty_fields():
    metadata = VideoMetadata(
        path="/tmp/fake.mp4",
        filename="sample_clip.mp4",
        extension=".mp4",
        size_bytes=1024,
    )
    analysis = AnalysisResult(visual_tags=["balanced_lighting", "dynamic_motion"])

    generated = compose_content(
        ComposeRequest(metadata=metadata, analysis=analysis, platform_key="tiktok")
    )

    assert generated.title
    assert generated.caption
    assert generated.hashtags.startswith("#")
