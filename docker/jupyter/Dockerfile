FROM apache/spark:4.0.2-python3

USER root

# Install notebook extras at image build time. Runtime `pip install` in
# docker-compose is brittle: it requires PyPI from inside the container and
# the previous multiline `bash -c` command dropped `--master` as a separate
# shell line when pip failed.
RUN pip install --no-cache-dir jupyterlab pandas pyarrow
