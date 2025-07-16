<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
usage: genai-perf profile [-h] [--audio-length-mean AUDIO_LENGTH_MEAN] [--audio-length-stddev AUDIO_LENGTH_STDDEV] [--audio-format {wav,mp3}] [--audio-depths [AUDIO_DEPTHS ...]]
                          [--audio-sample-rates [AUDIO_SAMPLE_RATES ...]] [--audio-num-channels {1,2}] [-m MODEL [MODEL ...]] [--model-selection-strategy {round_robin,random}] [--backend {tensorrtllm,vllm}]
                          [--endpoint ENDPOINT] [--endpoint-type {chat,completions,dynamic_grpc,embeddings,huggingface_generate,image_retrieval,nvclip,rankings,multimodal,generate,kserve,template,tensorrtllm_engine,vision}]
                          [--server-metrics-url SERVER_METRICS_URL [SERVER_METRICS_URL ...]] [--streaming] [-u URL] [--image-width-mean IMAGE_WIDTH_MEAN] [--image-width-stddev IMAGE_WIDTH_STDDEV]
                          [--image-height-mean IMAGE_HEIGHT_MEAN] [--image-height-stddev IMAGE_HEIGHT_STDDEV] [--image-format {png,jpeg}] [--batch-size-audio BATCH_SIZE_AUDIO] [--batch-size-image BATCH_SIZE_IMAGE]
                          [--batch-size-text BATCH_SIZE_TEXT] [--extra-inputs EXTRA_INPUTS] [--goodput GOODPUT [GOODPUT ...]] [--header HEADER] [--input-file INPUT_FILE] [--num-dataset-entries NUM_DATASET_ENTRIES]
                          [--num-prefix-prompts NUM_PREFIX_PROMPTS] [--output-tokens-mean OUTPUT_TOKENS_MEAN] [--output-tokens-mean-deterministic] [--output-tokens-stddev OUTPUT_TOKENS_STDDEV] [--random-seed RANDOM_SEED]
                          [--grpc-method GRPC_METHOD] [--synthetic-input-tokens-mean SYNTHETIC_INPUT_TOKENS_MEAN] [--synthetic-input-tokens-stddev SYNTHETIC_INPUT_TOKENS_STDDEV] [--prefix-prompt-length PREFIX_PROMPT_LENGTH]
                          [--warmup-request-count WARMUP_REQUEST_COUNT] [-v] [--artifact-dir ARTIFACT_DIR] [--checkpoint-dir CHECKPOINT_DIR] [--generate-plots] [--enable-checkpointing]
                          [--profile-export-file PROFILE_EXPORT_FILE] [--concurrency CONCURRENCY] [--measurement-interval MEASUREMENT_INTERVAL | --request-count REQUEST_COUNT] [--request-rate REQUEST_RATE]
                          [--fixed-schedule FIXED_SCHEDULE] [-s STABILITY_PERCENTAGE] [--num-sessions NUM_SESSIONS] [--session-concurrency SESSION_CONCURRENCY] [--session-delay-ratio SESSION_DELAY_RATIO]
                          [--session-turn-delay-mean SESSION_TURN_DELAY_MEAN] [--session-turn-delay-stddev SESSION_TURN_DELAY_STDDEV] [--session-turns-mean SESSION_TURNS_MEAN] [--session-turns-stddev SESSION_TURNS_STDDEV]
                          [--tokenizer TOKENIZER] [--tokenizer-revision TOKENIZER_REVISION] [--tokenizer-trust-remote-code]

Subcommand to profile LLMs and Generative AI models.

options:
  -h, --help            show this help message and exit

Audio Input:
  --audio-length-mean AUDIO_LENGTH_MEAN
                        The mean length of audio data in seconds. Default is 10 seconds.
  --audio-length-stddev AUDIO_LENGTH_STDDEV
                        The standard deviation of the length of audio data in seconds. Default is 0.
  --audio-format {wav,mp3}
                        The format of the audio data. Currently we support wav and mp3 format. Default is 'wav'.
  --audio-depths [AUDIO_DEPTHS ...]
                        A list of audio bit depths to randomly select from in bits. Default is [16].
  --audio-sample-rates [AUDIO_SAMPLE_RATES ...]
                        A list of audio sample rates to randomly select from in kHz. Default is [16].
  --audio-num-channels {1,2}
                        The number of audio channels to use for the audio data generation. Currently only 1 (mono) and 2 (stereo) are supported. Default is 1 (mono channel).

Endpoint:
  -m MODEL [MODEL ...], --model MODEL [MODEL ...]
                        The name of the model(s) to benchmark.
  --model-selection-strategy {round_robin,random}
                        When multiple model are specified, this is how a specific model should be assigned to a prompt. round_robin means that ith prompt in the list gets assigned to i mod len(models). random means that
                        assignment is uniformly random
  --backend {tensorrtllm,vllm}
                        When benchmarking Triton, this is the backend of the model.
  --endpoint ENDPOINT   Set a custom endpoint that differs from the OpenAI defaults.
  --endpoint-type {chat,completions,dynamic_grpc,embeddings,huggingface_generate,image_retrieval,nvclip,rankings,multimodal,generate,kserve,template,tensorrtllm_engine,vision}
                        The endpoint-type to send requests to on the server.
  --server-metrics-url SERVER_METRICS_URL [SERVER_METRICS_URL ...], --server-metrics-urls SERVER_METRICS_URL [SERVER_METRICS_URL ...]
                        The list of Triton server metrics URLs. These are used for Telemetry metric reporting with Triton. Example usage: --server-metrics-url http://server1:8002/metrics http://server2:8002/metrics
  --streaming           An option to enable the use of the streaming API.
  -u URL, --url URL     URL of the endpoint to target for benchmarking.

Image Input:
  --image-width-mean IMAGE_WIDTH_MEAN
                        The mean width of images when generating synthetic image data.
  --image-width-stddev IMAGE_WIDTH_STDDEV
                        The standard deviation of width of images when generating synthetic image data.
  --image-height-mean IMAGE_HEIGHT_MEAN
                        The mean height of images when generating synthetic image data.
  --image-height-stddev IMAGE_HEIGHT_STDDEV
                        The standard deviation of height of images when generating synthetic image data.
  --image-format {png,jpeg}
                        The compression format of the images. If format is not selected, format of generated image is selected at random

Input:
  --batch-size-audio BATCH_SIZE_AUDIO
                        The audio batch size of the requests GenAI-Perf should send. This is currently supported with the OpenAI `multimodal` endpoint type.
  --batch-size-image BATCH_SIZE_IMAGE
                        The image batch size of the requests GenAI-Perf should send. This is currently supported with the image retrieval endpoint type.
  --batch-size-text BATCH_SIZE_TEXT, --batch-size BATCH_SIZE_TEXT, -b BATCH_SIZE_TEXT
                        The text batch size of the requests GenAI-Perf should send. This is currently supported with the embeddings and rankings endpoint types.
  --extra-inputs EXTRA_INPUTS
                        Provide additional inputs to include with every request. You can repeat this flag for multiple inputs. Inputs should be in an 'input_name:value' format. Alternatively, a string representing a json
                        formatted dict can be provided.
  --goodput GOODPUT [GOODPUT ...], -g GOODPUT [GOODPUT ...]
                        An option to provide constraints in order to compute goodput. Specify goodput constraints as 'key:value' pairs, where the key is a valid metric name, and the value is a number representing either
                        milliseconds or a throughput value per second. For example, 'request_latency:300' or 'output_token_throughput_per_user:600'. Multiple key:value pairs can be provided, separated by spaces.
  --header HEADER, -H HEADER
                        Add a custom header to the requests. Headers must be specified as 'Header:Value'. You can repeat this flag for multiple headers.
  --input-file INPUT_FILE
                        The input file or directory containing the content to use for profiling. Each line should be a JSON object with a 'text' or 'image' field in JSONL format. Example: {"text": "Your prompt here"}. To
                        use synthetic files for a converter that needs multiple files, prefix the path with 'synthetic:', followed by a comma-separated list of filenames. The synthetic filenames should not have extensions.
                        For example, 'synthetic:queries,passages'. For payload data, prefix the path with 'payload:', followed by a JSON string representing a payload object. The payload should contain a 'timestamp' field
                        and you can optionally add 'input_length', 'output_length','text_input', 'session_id', 'hash_ids', and 'priority'. Example: 'payload:{"timestamp": 123.45, "input_length": 10, "output_length": 12,
                        "session_id": 1, "priority": 5, "text_input": "Your prompt here"}'.
  --num-dataset-entries NUM_DATASET_ENTRIES, --num-prompts NUM_DATASET_ENTRIES
                        The number of unique payloads to sample from. These will be reused until benchmarking is complete.
  --num-prefix-prompts NUM_PREFIX_PROMPTS
                        The number of prefix prompts to select from. If this value is not zero, these are prompts that are prepended to input prompts. This is useful for benchmarking models that use a K-V cache.
  --output-tokens-mean OUTPUT_TOKENS_MEAN, --osl OUTPUT_TOKENS_MEAN
                        The mean number of tokens in each output. Ensure the --tokenizer value is set correctly.
  --output-tokens-mean-deterministic
                        When using --output-tokens-mean, this flag can be set to improve precision by setting the minimum number of tokens equal to the requested number of tokens. This is currently supported with Triton.
                        Note that there is still some variability in the requested number of output tokens, but GenAi-Perf attempts its best effort with your model to get the right number of output tokens.
  --output-tokens-stddev OUTPUT_TOKENS_STDDEV
                        The standard deviation of the number of tokens in each output. This is only used when --output-tokens-mean is provided.
  --random-seed RANDOM_SEED
                        The seed used to generate random values. If not provided, a random seed will be used.
  --grpc-method GRPC_METHOD
                        A fully-qualified gRPC method name in '<package>.<service>/<method>' format. The option is only supported by dynamic gRPC service kind and is required to identify the RPC to use when sending requests
                        to the server.
  --synthetic-input-tokens-mean SYNTHETIC_INPUT_TOKENS_MEAN, --isl SYNTHETIC_INPUT_TOKENS_MEAN
                        The mean of number of tokens in the generated prompts when using synthetic data.
  --synthetic-input-tokens-stddev SYNTHETIC_INPUT_TOKENS_STDDEV
                        The standard deviation of number of tokens in the generated prompts when using synthetic data.
  --prefix-prompt-length PREFIX_PROMPT_LENGTH
                        The number of tokens in each prefix prompt. This value is only used if --num-prefix-prompts is positive. Note that due to the prefix and user prompts being concatenated, the number of tokens in the
                        final prompt may be off by one.
  --warmup-request-count WARMUP_REQUEST_COUNT, --num-warmup-requests WARMUP_REQUEST_COUNT
                        The number of warmup requests to send before benchmarking.

Other:
  -v, --verbose         An option to enable verbose mode.

Output:
  --artifact-dir ARTIFACT_DIR
                        The directory to store all the (output) artifacts generated by GenAI-Perf and Perf Analyzer.
  --checkpoint-dir CHECKPOINT_DIR
                        The directory to store/restore the checkpoint generated by GenAI-Perf.
  --generate-plots      An option to enable the generation of plots.
  --enable-checkpointing
                        Enables checkpointing of the GenAI-Perf state. This is useful for running GenAI-Perf in a stateful manner.
  --profile-export-file PROFILE_EXPORT_FILE
                        The path where the perf_analyzer profile export will be generated. By default, the profile export will be to profile_export.json. The genai-perf file will be exported to
                        <profile_export_file>_genai_perf.csv. For example, if the profile export file is profile_export.json, the genai-perf file will be exported to profile_export_genai_perf.csv.

Profiling:
  --concurrency CONCURRENCY
                        The concurrency value to benchmark.
  --measurement-interval MEASUREMENT_INTERVAL, -p MEASUREMENT_INTERVAL
                        The time interval used for each measurement in milliseconds. Perf Analyzer will sample a time interval specified and take measurement over the requests completed within that time interval. When using
                        the default stability percentage, GenAI-Perf will benchmark for 3*(measurement_interval) milliseconds.
  --request-count REQUEST_COUNT, --num-requests REQUEST_COUNT
                        The number of requests to use for measurement.
  --request-rate REQUEST_RATE
                        Sets the request rate for the load generated by PA.
  --fixed-schedule FIXED_SCHEDULE
                        An option to enable fixed schedule (trace) inference load mode.
  -s STABILITY_PERCENTAGE, --stability-percentage STABILITY_PERCENTAGE
                        The allowed variation in latency measurements when determining if a result is stable. The measurement is considered as stable if the ratio of max / min from the recent 3 measurements is within
                        (stability percentage) in terms of both infer per second and latency.

Session:
  --num-sessions NUM_SESSIONS
                        The number of sessions to simulate.
  --session-concurrency SESSION_CONCURRENCY
                        The number of concurrent sessions to benchmark.
  --session-delay-ratio SESSION_DELAY_RATIO
                        A ratio to scale multi-turn delays when using a payload file. For example, a value of 0.5 will halve the specified delays.
  --session-turn-delay-mean SESSION_TURN_DELAY_MEAN
                        The mean delay (in ms) between turns in a session.
  --session-turn-delay-stddev SESSION_TURN_DELAY_STDDEV
                        The standard deviation (in ms) of the delay between turns in a session.
  --session-turns-mean SESSION_TURNS_MEAN
                        The mean number of turns per session.
  --session-turns-stddev SESSION_TURNS_STDDEV
                        The standard deviation of the number of turns per session.

Tokenizer:
  --tokenizer TOKENIZER
                        The HuggingFace tokenizer to use to interpret token metrics from prompts and responses. The value can be the name of a tokenizer or the filepath of the tokenizer. The default value is the model name.
  --tokenizer-revision TOKENIZER_REVISION
                        The specific model version to use. It can be a branch name, tag name, or commit ID.
  --tokenizer-trust-remote-code
                        Allow custom tokenizer to be downloaded and executed. This carries security risks and should only be used for repositories you trust. This is only necessary for custom tokenizers stored in
                        HuggingFace Hub.
