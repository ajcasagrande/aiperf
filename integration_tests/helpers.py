#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import pandas as pd

from aiperf.common.messages import ProfileResultsMessage
from aiperf.common.record_models import RequestRecord
from aiperf.services.records_manager.records_manager import record_from_dataframe


async def post_process_records(
    records: list[RequestRecord],
) -> ProfileResultsMessage | None:
    """Post process the records."""
    if not records:
        return None

    valid_records = [record for record in records if record.valid]
    # Extract time to first response values
    time_to_first_token_values = [
        record.time_to_first_response_ns for record in valid_records
    ]
    time_to_second_token_values = [
        record.time_to_second_response_ns for record in valid_records
    ]
    time_to_last_token_values = [
        record.time_to_last_response_ns for record in valid_records
    ]
    inter_token_latency_values = [
        record.inter_token_latency_ns for record in valid_records
    ]

    # Create single DataFrame with all metrics
    metrics_df = pd.DataFrame(
        {
            "ttft_ns": time_to_first_token_values,
            "ttst_ns": time_to_second_token_values,
            "ttlt_ns": time_to_last_token_values,
            "itl_ns": inter_token_latency_values,
        }
    )

    # Create Record objects (converting from ns to ms)
    ttft_record = record_from_dataframe(
        df=metrics_df,
        column_name="ttft_ns",
        name="Time to First Token",
        unit="ms",
        streaming_only=True,
    )

    ttst_record = record_from_dataframe(
        df=metrics_df,
        column_name="ttst_ns",
        name="Time to Second Token",
        unit="ms",
        streaming_only=True,
    )

    ttlt_record = record_from_dataframe(
        df=metrics_df,
        column_name="ttlt_ns",
        name="Time to Last Token",
        unit="ms",
        streaming_only=False,
    )

    itl_record = record_from_dataframe(
        df=metrics_df,
        column_name="itl_ns",
        name="Inter Token Latency",
        unit="ms",
        streaming_only=True,
    )

    # Create and return ProfileResultsMessage
    return ProfileResultsMessage(
        service_id="aiohttp",
        records=[ttft_record, ttst_record, ttlt_record, itl_record],
    )
