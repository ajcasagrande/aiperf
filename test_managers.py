import asyncio
import logging
import sys
import time
from aiperf.dataset.dataset_manager import DatasetManager
from aiperf.records.records_manager import RecordsManager
from aiperf.config.config_models import DatasetConfig, MetricsConfig
from aiperf.common.models import Conversation, ConversationTurn, Record, Metric
from aiperf.common.memory_communication import MemoryCommunication

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_managers")


async def test_dataset_manager():
    logger.info("Testing DatasetManager...")

    # Create communication instance
    comm = MemoryCommunication(client_id="test_client")
    await comm.initialize()

    # Create dataset config for synthetic data
    dataset_config = DatasetConfig(
        name="test_dataset",
        source_type="synthetic",
        modality="text",
        synthetic_params={
            "pre_generate": 2  # Generate 2 synthetic conversations
        },
    )

    # Initialize dataset manager
    dataset_manager = DatasetManager(dataset_config, communication=comm)
    success = await dataset_manager.initialize()

    if success:
        logger.info("DatasetManager initialized successfully")

        # Test getting a conversation
        conversation = Conversation(
            conversation_id="test_conversation", metadata={"test": True}
        )

        # Add some turns
        turn1 = ConversationTurn(
            request="What is artificial intelligence?",
            response="Artificial intelligence refers to systems designed to perform tasks that typically require human intelligence.",
        )
        conversation.turns.append(turn1)

        turn2 = ConversationTurn(
            request="Give me examples of AI applications.",
            response="Examples of AI applications include natural language processing, computer vision, recommendation systems, and autonomous vehicles.",
        )
        conversation.turns.append(turn2)

        logger.info(
            f"Created test conversation with ID: {conversation.conversation_id}"
        )
        logger.info(f"Number of turns: {len(conversation.turns)}")

        for i, turn in enumerate(conversation.turns):
            logger.info(f"Turn {i + 1}: {turn.request}")
    else:
        logger.error("Failed to initialize DatasetManager")

    return dataset_manager, comm, conversation


async def test_records_manager(dataset_manager, comm, conversation):
    logger.info("Testing RecordsManager...")

    # Create metrics config
    metrics_config = MetricsConfig(
        output_path="test_records.json",
        enabled_metrics=["latency", "tokens", "success"],
    )

    # Initialize records manager
    records_manager = RecordsManager(metrics_config, communication=comm)
    success = await records_manager.initialize()

    if success:
        logger.info("RecordsManager initialized successfully")

        # Create a test record
        if conversation:
            # Create some metrics
            metrics = [
                Metric(name="latency", value=1.5, unit="s"),
                Metric(name="tokens", value=150, unit="tokens"),
                Metric(name="success", value=True),
            ]

            # Create a record
            record = Record(
                record_id="test_record_1",
                conversation=conversation,
                metrics=metrics,
                raw_data={"test_key": "test_value"},
            )

            # Store the record
            success = await records_manager.store_record(record)

            if success:
                logger.info("Record stored successfully")

                # Test getting the record
                retrieved_record = await records_manager.get_record("test_record_1")

                if retrieved_record:
                    logger.info(
                        f"Retrieved record with ID: {retrieved_record.record_id}"
                    )
                    logger.info(f"Number of metrics: {len(retrieved_record.metrics)}")

                    # Test getting records with filters
                    filtered_records = await records_manager.get_records(
                        {"conversation_id": conversation.conversation_id}
                    )

                    logger.info(
                        f"Found {len(filtered_records)} records with matching conversation ID"
                    )

                    # Get stats
                    stats = await records_manager.get_stats()
                    logger.info(f"Records stats: {stats}")

                    # Flush records to disk
                    await records_manager._flush_records_to_disk()
                    logger.info("Records flushed to disk")
                else:
                    logger.error("Failed to retrieve record")
            else:
                logger.error("Failed to store record")
    else:
        logger.error("Failed to initialize RecordsManager")

    return records_manager


async def main():
    logger.info("Starting managers test...")

    try:
        # Test dataset manager
        dataset_manager, comm, conversation = await test_dataset_manager()

        # Test records manager
        records_manager = await test_records_manager(
            dataset_manager, comm, conversation
        )

        # Shut down both managers
        logger.info("Shutting down managers...")
        await records_manager.shutdown()
        await dataset_manager.shutdown()
        await comm.shutdown()

        logger.info("Test completed successfully!")
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
