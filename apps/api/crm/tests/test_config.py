from pathlib import Path
from src.config import load_config

def test_load_config(tmp_path: Path):
    config_file = tmp_path / "test_config.ini"
    config_content = """[paths]
output_format = pdf
output = my_custom_output

[mailjet]
api_key = test_key
api_secret = test_secret
from_email = test@example.com
from_name = Test Doctor
sandbox = true

[mail]
template_id = 12345
subject = Test Subject

[ai_provider_openai]
api_key = openai_key
base_url = https://api.openai.com/v1
model = gpt-4o

[ai_feature_prefill]
provider = openai
prompt = prompts/prefill.txt
enabled = true
"""
    config_file.write_text(config_content, encoding="utf-8")
    
    cfg = load_config(config_file)
    
    assert cfg.paths.output_format == "pdf"
    assert cfg.paths.output.name == "my_custom_output"
    assert cfg.mailjet.api_key == "test_key"
    assert cfg.mailjet.api_secret == "test_secret"
    assert cfg.mailjet.from_email == "test@example.com"
    assert cfg.mailjet.from_name == "Test Doctor"
    assert cfg.mailjet.sandbox is True
    
    assert cfg.mail.template_id == 12345
    assert cfg.mail.subject == "Test Subject"
    
    assert cfg.ai.provider("openai") is not None
    assert cfg.ai.provider("openai").api_key == "openai_key"
    assert cfg.ai.provider("openai").model == "gpt-4o"
    
    assert cfg.ai.feature("prefill") is not None
    assert cfg.ai.feature("prefill").provider == "openai"
    assert cfg.ai.feature("prefill").enabled is True
