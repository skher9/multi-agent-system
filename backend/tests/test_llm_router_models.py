from llm_router.models import ESCALATION_MODEL, FIXED_MODEL, MODELS, Role, model_for


def test_every_role_has_a_model() -> None:
    assert set(MODELS) == set(Role)


def test_model_ids_use_openrouter_provider_slash_name_format() -> None:
    for model_id in [*MODELS.values(), ESCALATION_MODEL]:
        provider, _, name = model_id.partition("/")
        assert provider and name, model_id


def test_model_for_returns_the_role_model() -> None:
    assert model_for(Role.DEVELOPER) == "deepseek/deepseek-v4.1-flash"
    assert model_for(Role.TICKET_READER) == "deepseek/deepseek-v4.1-flash"


def test_escalation_overrides_the_role_model() -> None:
    for role in set(Role) - FIXED_MODEL:
        assert model_for(role, escalate=True) == "deepseek/deepseek-v4-pro"


def test_the_grader_is_always_its_own_model_from_another_family() -> None:
    builders = {MODELS[role].split("/")[0] for role in set(Role) - {Role.GRADER}}
    for kwargs in ({}, {"escalate": True}, {"strong": True}):
        model = model_for(Role.GRADER, **kwargs)
        assert model == MODELS[Role.GRADER]
        assert model.split("/")[0] not in builders


def test_role_values_fit_the_agent_runs_column() -> None:
    # agent_runs.role is String(32)
    assert all(len(role.value) <= 32 for role in Role)
