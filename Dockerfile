FROM python:3.11-slim

LABEL org.opencontainers.image.title="SDC Tools"
LABEL org.opencontainers.image.description="Validate, generate, and analyze Synopsys Design Constraint (SDC) files"
LABEL org.opencontainers.image.source="https://github.com/RAMA-L7/sdc-tools"
LABEL org.opencontainers.image.license="MIT"

WORKDIR /app

# Install system deps for Streamlit
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Copy project files
COPY cli.py checker.py generator.py corner_manager.py mmc.py \
     tcl_resolver.py wildcard_analyzer.py constraint_diff.py \
     clock_relations.py rules_registry.py reporter.py coverage.py \
     custom_rules.py custom_rules_example.yaml \
     .pre-commit-config.yaml .pre-commit-hooks/ \
     ./

# Copy samples
COPY samples/ ./samples/

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir pyyaml

# CLI usage
ENTRYPOINT ["python", "cli.py"]
CMD ["--help"]

# For web UI:
# docker run -p 8501:8501 sdc-tools streamlit run app.py