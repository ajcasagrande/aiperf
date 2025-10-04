from setuptools import setup, find_packages

setup(
    name='aiperf',
    version='0.1.0',
    author='Your Name',
    author_email='your.email@example.com',
    description='A modular, high-throughput benchmarking tool for large-scale inference infrastructure.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/yourusername/aiperf',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=[
        # List your project dependencies here
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)