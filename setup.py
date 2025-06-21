from setuptools import setup, find_packages

setup(
    name='cbudget',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'PyYAML',      # For parsing YAML config files
        'requests',    # For HTTP requests to WattTime API
        # 'python-hcl2', # For the need to parse HCL directly for Carbonifer integration, or use a subprocess
        # 'click',       # For building CLI if not using argparse
    ],
    entry_points={
        'console_scripts': [
            'cbudget=cbudget.cli:main',
        ],
    },
    author='Arlo Nguyen',
    description='A wrapper for carbon budgeting in IaC provisioning workflows within CI/CD pipelines.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/arlonguy/CarbonBudgetWrapper', # the repo URL
)
