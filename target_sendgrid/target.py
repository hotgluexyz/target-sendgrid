"""sendgrid target class."""

from __future__ import annotations

from singer_sdk import typing as th
from target_hotglue.target import TargetHotglue
import copy
from singer_sdk.mapper import PluginMapper

from target_sendgrid.sinks import (
    sendgridSink,
    ContactsSink,
    CustomersSink
)


class TargetSendgrid(TargetHotglue):
    """Sample target for sendgrid."""
    name = "target-sendgrid"

    config_jsonschema = th.PropertiesList(
        th.Property(
            "auth_token",
            th.StringType, # Flag config as protected.
            description="The path to the target output file",
        ),
        th.Property(
            'unsubscribe_list_id',
            th.StringType,
            description = 'SendGrid List ID of the Unsubscribe list'

        )
    ).to_dict()

    default_sink_class = sendgridSink
    SINK_TYPES = [ContactsSink, CustomersSink]
    MAX_PARALLELISM = 1


if __name__ == "__main__":
    TargetSendgrid.cli()
