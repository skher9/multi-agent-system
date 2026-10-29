from llm_router.models import ESCALATION_MODEL, MODELS, Role, model_for


def test_every_role_has_a_model() -> None:
    assert set(MODELS) == set(Role)


def test_model_ids_use_openrouter_provider_slash_name_format() -> None:
    for model_id in [*MODELS.values(), ESCALATION_MODEL]:
        provider, _, name = model_id.partition("/")
        assert provider and name, model_id


def test_model_for_returns_the_role_model() -> None:
    assert model_for(Role.DEVELOPER) == "minimax/minimax-m3"
    assert model_for(Role.TICKET_READER) == "deepseek/deepseek-v4.1-flash"


def test_escalation_overrides_the_role_model() -> None:
    for role in Role:
        assert model_for(role, escalate=True) == "z-ai/glm-5.2"


def test_role_values_fit_the_agent_runs_column() -> None:
    # agent_runs.role is String(32)
    assert all(len(role.value) <= 32 for role in Role)
