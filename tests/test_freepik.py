"""Test Freepik visual honeytoken generation."""
import sys
sys.path.insert(0, '.')


def test_visual_honeytoken_generation():
    """Test basic visual honeytoken generation."""
    from backend.tools.visual_honeytoken import generate_visual_honeytoken

    result = generate_visual_honeytoken("architecture_diagram")

    assert "url" in result
    assert "canary_id" in result
    assert result["canary_id"].startswith("img-")
    assert result["asset_type"] == "architecture_diagram"
    assert "source" in result
    assert "generated_at" in result
    print(f"✓ Generated: {result['url'][:50]}...")
    print(f"✓ Canary ID: {result['canary_id']}")
    print(f"✓ Source: {result['source']}")


def test_all_asset_types():
    """Test all supported asset types."""
    from backend.tools.visual_honeytoken import generate_visual_honeytoken

    for asset_type in ["architecture_diagram", "admin_screenshot", "database_schema", "network_topology"]:
        result = generate_visual_honeytoken(asset_type)
        assert result["asset_type"] == asset_type
        assert result["canary_id"].startswith("img-")
        assert result["url"].startswith("http")
        print(f"✓ {asset_type}: OK")


def test_with_context():
    """Test generation with custom context."""
    from backend.tools.visual_honeytoken import generate_visual_honeytoken

    result = generate_visual_honeytoken("architecture_diagram", context="microservices, kubernetes")

    assert result["asset_type"] == "architecture_diagram"
    assert result["canary_id"].startswith("img-")
    print(f"✓ Context customization: OK")


def test_unique_canary_ids():
    """Verify each generation produces unique canary IDs."""
    from backend.tools.visual_honeytoken import generate_visual_honeytoken

    canary_ids = set()
    for _ in range(5):
        result = generate_visual_honeytoken("architecture_diagram")
        canary_ids.add(result["canary_id"])

    assert len(canary_ids) == 5, "Canary IDs should be unique"
    print(f"✓ Unique canary IDs: {len(canary_ids)} unique IDs generated")


if __name__ == "__main__":
    print("Running visual honeytoken tests...\n")
    test_visual_honeytoken_generation()
    print()
    test_all_asset_types()
    print()
    test_with_context()
    print()
    test_unique_canary_ids()
    print("\n✅ ALL TESTS PASSED!")
