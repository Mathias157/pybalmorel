"""
Weather-Year Naming and Filtering Regression Tests

Covers two bug classes found while investigating a GREAT-repo report of
technologies leaking past turbine_to_keep/PV_to_keep and of INVDATA linking
areas built under one name to investment options built under another:

1. GGG_renewable / INVDATASET_renewable / AAA_renewable naming must come from
   the shared per-category templates in additional_inc.py, not three
   independently hand-typed f-strings (see pybalmorel ADR 0003).
2. combine_technology_timeseries_files must re-apply turbine_to_keep/
   tech_to_keep to files already on disk, since export_timeseries_to_xlsx
   never deletes a turbine's files just because it's no longer enabled (see
   pybalmorel ADR 0004).

Created on 09.09.2026
"""
# %% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import os

import pandas as pd
import pytest

from pybalmorel.weatheryear.additional_inc import (
    _SOLAR_TEMPLATES,
    _WIND_TEMPLATES,
    _template_for,
    build_AAA,
    build_GGG,
    build_INVDATA_renewable,
    build_INVDATASET,
)
from pybalmorel.weatheryear.config_models import (
    AdditionalIncConfig,
    AnnuityCalculationConfig,
    RegionsConfig,
    WeatherYearConfig,
)
from pybalmorel.weatheryear.exceptions import EmptyMergeResultError
from pybalmorel.weatheryear.get_GKFX_func import _drop_unnamed_columns
from pybalmorel.weatheryear.to_balmorel import combine_technology_timeseries_files


def _additional_inc_config(**overrides) -> AdditionalIncConfig:
    defaults = dict(
        regions_to_keep=RegionsConfig(onshore=["IE", "PT"], offshore=["IE_OFF"]),
        rg_to_keep={
            "Future_Onshore": ["RGA"],
            "Future_Offshore_bottom_fixed": ["RGA"],
            "PV_Utility_scale_no_tracking": ["RGA"],
        },
        turbine_to_keep=["SP277-HH100"],
        tech_to_keep=["Future_Onshore", "PV_Utility_scale_no_tracking"],
        annuitycg_calculation=AnnuityCalculationConfig(
            debt_share=0.0, discount_rate=0.04, interest_rate=0.04
        ),
        vre_potentials="unused.xlsx",
        vre_tech_costs="unused.xlsx",
        existing_wind_cap="unused.xlsx",
        existing_solar_cap="unused.xlsx",
    )
    defaults.update(overrides)
    return AdditionalIncConfig(**defaults)


# %% ------------------------------- ###
###   1. GGG/INVDATASET/AAA naming   ###
### ------------------------------- ###


def test_ggg_invdataset_aaa_share_the_same_turbine_and_rg(tmp_path):
    """The three set domains keep their own distinct spellings, but all three
    must be built from the same (turbine, rg) pair for a given category - a
    hand-typed divergence between them is exactly what broke INVDATA linking."""
    os.makedirs(tmp_path / "to_balmorel")
    config = _additional_inc_config()
    techs = {"wind": {"Future_Onshore"}, "solar": set()}
    turbines = {"onshore": {"SP277-HH100"}, "offshore": set()}

    invdataset_df = build_INVDATASET(config, str(tmp_path), techs, turbines)
    ggg_df = build_GGG(config, str(tmp_path), techs, turbines)
    aaa_df = build_AAA(config, str(tmp_path), techs, turbines)

    assert "VRE-ONS_SP277-HH100_RG1" in set(invdataset_df["INVDATASET_renewables"])
    # build_GGG returns the df already renamed to its G_renewable column (the
    # form build_ALLOWEDINV/build_AGKN match against).
    assert "GNR_WT-SP277-HH100_ONS_RG1_Y-2020" in set(ggg_df["G_renewable"])
    assert "IE_VRE-ONS_SP277-HH100_RG1" in set(aaa_df["AAA_renewable"])
    assert "PT_VRE-ONS_SP277-HH100_RG1" in set(aaa_df["AAA_renewable"])


def test_invdata_links_every_region_to_the_matching_invdataset_member(tmp_path):
    os.makedirs(tmp_path / "to_balmorel")
    config = _additional_inc_config()
    techs = {"wind": {"Future_Onshore"}, "solar": set()}
    turbines = {"onshore": {"SP277-HH100"}, "offshore": set()}

    invdataset_df = build_INVDATASET(config, str(tmp_path), techs, turbines)
    aaa_df = build_AAA(config, str(tmp_path), techs, turbines)
    invdata_df = build_INVDATA_renewable(invdataset_df, aaa_df, str(tmp_path))

    links = set(invdata_df["INVDATA_renewable"])
    assert "INVDATA('IE_VRE-ONS_SP277-HH100_RG1','VRE-ONS_SP277-HH100_RG1')=1 ;" in links
    assert "INVDATA('PT_VRE-ONS_SP277-HH100_RG1','VRE-ONS_SP277-HH100_RG1')=1 ;" in links


def test_template_for_raises_for_unregistered_category():
    """_template_for is the single lookup build_GGG/build_INVDATASET/build_AAA
    all share (ADR 0003) - if a future edit adds a new elif branch to one of
    those builders without registering a matching _WIND_TEMPLATES/
    _SOLAR_TEMPLATES entry, this must raise loudly rather than KeyError being
    silently avoided by every caller happening to gate on the same substrings."""
    with pytest.raises(KeyError):
        _template_for("Future_Offshore_new_type", _WIND_TEMPLATES)
    with pytest.raises(KeyError):
        _template_for("PV_New_type", _SOLAR_TEMPLATES)


def test_all_future_categories_have_registered_templates():
    for tech in [
        "Future_Onshore",
        "Future_Offshore_bottom_fixed",
        "Future_Offshore_floating",
    ]:
        template = _template_for(tech, _WIND_TEMPLATES)
        assert {"ggg", "invdataset", "aaa"} <= template.keys()
    for tech in [
        "PV_Rooftop",
        "PV_Utility_scale_no_tracking",
        "PV_Utility_scale_tracking",
    ]:
        template = _template_for(tech, _SOLAR_TEMPLATES)
        assert {"ggg", "ggg_existing", "invdataset", "aaa"} <= template.keys()


# %% ------------------------------------------- ###
### 2. combine_technology_timeseries_files filter ###
### ------------------------------------------- ###


def _write_timeseries_xlsx(path: str, column: str, values: list[float]) -> None:
    df = pd.DataFrame({"time": range(len(values)), column: values})
    df.to_excel(path, index=False)


def _weatheryear_config(**overrides) -> WeatherYearConfig:
    defaults = dict(
        corres_results={},
        regions_to_keep=RegionsConfig(onshore=["IE"], offshore=[]),
        rg_to_keep={"Future_Onshore": ["RGA"]},
        turbine_to_keep=["SP277-HH100"],
        tech_to_keep=["Future_Onshore"],
    )
    defaults.update(overrides)
    return WeatherYearConfig(**defaults)


def test_combine_technology_timeseries_files_drops_stale_excluded_turbine(tmp_path):
    """export_timeseries_to_xlsx never deletes a turbine's files just because
    turbine_to_keep no longer includes it - combine_technology_timeseries_files
    must re-check turbine_to_keep itself rather than trusting os.listdir()."""
    folder = "Future_Onshore"
    raw_dir = os.path.join(tmp_path, folder, "raw")
    os.makedirs(raw_dir)
    _write_timeseries_xlsx(
        os.path.join(raw_dir, "SP277_HH100_RGA_raw.xlsx"), "P", [1.0, 2.0]
    )
    # Stale file from a run under an older turbine_to_keep that included SP335-HH100.
    _write_timeseries_xlsx(
        os.path.join(raw_dir, "SP335_HH100_RGA_raw.xlsx"), "P", [9.0, 9.0]
    )

    config = _weatheryear_config()
    combined = combine_technology_timeseries_files(folder, str(tmp_path), "raw", config)

    columns = list(combined.columns)
    assert any("SP277-HH100" in c for c in columns)
    assert not any("SP335-HH100" in c for c in columns)


def test_combine_technology_timeseries_files_raises_when_all_files_excluded(tmp_path):
    folder = "Future_Onshore"
    raw_dir = os.path.join(tmp_path, folder, "raw")
    os.makedirs(raw_dir)
    _write_timeseries_xlsx(
        os.path.join(raw_dir, "SP335_HH100_RGA_raw.xlsx"), "P", [9.0, 9.0]
    )

    config = _weatheryear_config()
    with pytest.raises(EmptyMergeResultError):
        combine_technology_timeseries_files(folder, str(tmp_path), "raw", config)


# %% ------------------------------- ###
###   3. GKFX Unnamed: columns       ###
### ------------------------------- ###


def test_drop_unnamed_columns_strips_pandas_synthesized_columns():
    df = pd.DataFrame(
        {
            "Region": ["IE"],
            "Technology": ["RG1"],
            2020: [1.0],
            "Unnamed: 41": [float("nan")],
            "Unnamed: 42": [0.0],
        }
    )
    cleaned = _drop_unnamed_columns(df)
    assert list(cleaned.columns) == ["Region", "Technology", 2020]
