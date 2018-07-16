#!/usr/bin/env python

import os
import io
import sys
import shutil
import subprocess
import tempfile

import click
import ruamel.yaml as ryaml
import jinja2

HERE = os.path.abspath(os.path.dirname(__file__))


def load_settings(service, config):
    service_configs_filepath = os.path.join(HERE, 'services', '{}.yaml'.format(service))
    yaml = ryaml.YAML()
    try:
        with io.open(service_configs_filepath, encoding='utf-8') as f:
            descriptor = yaml.load(f)
    except Exception as e:
        return None, 'Failed to load descriptor for service [{}]: {}'.format(service, e)
    else:
        if not descriptor or 'configs' not in descriptor:
            return None, 'Service descriptor invalid or empty'
        if config not in descriptor['configs']:
            return None, 'Config definition not found: {}'.format(config)

        def deep_format(obj):
            if isinstance(obj, dict):
                return {k: deep_format(v) for k, v in obj.items()}
            if isinstance(obj, str):
                return obj.format(service=service, config=config)
            return obj

        settings_common = descriptor.get('common', {})
        settings = deep_format(settings_common)
        settings.update(descriptor['configs'][config] or {})
        settings['SERVICE'] = service
        settings['CONFIG'] = config
        settings['HOME'] = HERE
        settings['PYTHON_CMD'] = sys.executable
        return settings, None


def render_template(localpath, context):
    loader = jinja2.FileSystemLoader(HERE)
    env = jinja2.Environment(loader=loader)
    env.undefined = jinja2.StrictUndefined
    template = env.get_template(localpath)
    result = template.render(context)
    return result


def ensure_dir_exists(path):
    if not os.path.exists(path):
        os.makedirs(path)
    else:
        if not os.path.isdir(path):
            raise Exception('Target path is not directory: {}'.format(path))


def backup_nginx_files(config, filepath):
    targetroot = '/etc/nginx'
    targetincludes = os.path.join(targetroot, 'includes', config)
    targetcerts = os.path.join(targetroot, 'certs', config)
    siteconf_dst = os.path.join(targetroot, 'sites-available', '{}.conf'.format(config))
    siteconf_linkname = os.path.join(targetroot, 'sites-enabled', os.path.basename(siteconf_dst))

    command = 'tar --create --file {} --files-from /dev/null'.format(filepath)
    subprocess.run(command.split(), check=True)

    tar_append_prefix = 'tar --append --directory {} --file {}'.format(targetroot, filepath)

    def append_to_archive(dst):
        if os.path.exists(os.path.join(targetroot, dst)):
            command = '{} {}'.format(tar_append_prefix, dst)
            subprocess.run(command.split(), check=True)

    append_to_archive('sites-available/{}.conf'.format(config))
    append_to_archive('sites-enabled/{}.conf'.format(config))
    append_to_archive('includes/{}'.format(config))
    append_to_archive('certs/{}'.format(config))


def restore_nginx_files(config, filepath):
    targetroot = '/etc/nginx'
    targetincludes = os.path.join(targetroot, 'includes', config)
    targetcerts = os.path.join(targetroot, 'certs', config)
    siteconf_dst = os.path.join(targetroot, 'sites-available', '{}.conf'.format(config))
    siteconf_linkname = os.path.join(targetroot, 'sites-enabled', os.path.basename(siteconf_dst))
    if os.path.exists(siteconf_linkname):
        os.remove(siteconf_linkname)
    if os.path.exists(siteconf_dst):
        os.remove(siteconf_dst)
    shutil.rmtree(targetincludes, ignore_errors=True)
    shutil.rmtree(targetcerts, ignore_errors=True)
    command = 'tar --extract --directory {} --file {}'.format(targetroot, filepath)
    subprocess.run(command.split(), check=True)


def install_nginx_files(config, settings):

    def copy_from_template(context, localtemplatepath, dstpath):
        result = render_template(localtemplatepath, context)
        with io.open(dstpath, 'w', encoding='utf-8') as ostream:
            shutil.copyfileobj(io.StringIO(result), ostream)

    targetroot = '/etc/nginx'
    targetincludes = os.path.join(targetroot, 'includes', config)
    targetcerts = os.path.join(targetroot, 'certs', config)
    ensure_dir_exists(targetcerts)
    certfiles = settings.get('certs', []) or []
    for filename in certfiles:
        src = os.path.join(HERE, 'nginxsite', 'certs', filename)
        shutil.copy(src, targetcerts)
    ensure_dir_exists(targetincludes)
    includefiles = settings.get('includes', []) or []
    for filename in includefiles:
        src = os.path.join('nginxsite', 'includes', filename)
        dst = os.path.join(targetincludes, filename)
        copy_from_template(settings, src, dst)
    mkdirs = settings.get('mkdirs', []) or []
    for dirpath in mkdirs:
        ensure_dir_exists(dirpath)
    siteconf_src = os.path.join('nginxsite', '{}.conf'.format(config))
    siteconf_dst = os.path.join(targetroot, 'sites-available', '{}.conf'.format(config))
    copy_from_template(settings, siteconf_src, siteconf_dst)
    siteconf_linkname = os.path.join(targetroot, 'sites-enabled', os.path.basename(siteconf_dst))
    if os.path.exists(siteconf_linkname):
        os.remove(siteconf_linkname)
    os.symlink(siteconf_dst, siteconf_linkname)


def uninstall_nginx_files(config, settings):
    targetroot = '/etc/nginx'
    targetincludes = os.path.join(targetroot, 'includes', config)
    targetcerts = os.path.join(targetroot, 'certs', config)
    siteconf_dst = os.path.join(targetroot, 'sites-available', '{}.conf'.format(config))
    siteconf_linkname = os.path.join(targetroot, 'sites-enabled', os.path.basename(siteconf_dst))
    if os.path.exists(siteconf_linkname):
        os.remove(siteconf_linkname)
    if os.path.exists(siteconf_dst):
        os.remove(siteconf_dst)
    if os.path.exists(targetincludes):
        shutil.rmtree(targetincludes)
    if os.path.exists(targetcerts):
        shutil.rmtree(targetcerts)


def test_nginx_config():
    command = 'nginx -t'
    subprocess.run(command.split(), check=True)


def reload_nginx_config():
    command = 'nginx -s reload'
    subprocess.run(command.split(), check=True)


@click.group()
def cli():
    """Tool for service control"""
    pass


@cli.command()
@click.argument('service')
@click.argument('config')
def install(service, config):
    """Install service configuration"""
    print('Setting up service [{}] for config [{}]...'.format(service, config))
    settings, error = load_settings(service, config)
    if error is not None:
        print('ERROR:', error, file=sys.stderr)
        sys.exit(1)
    try:
        if service == 'nginxsite':
            with tempfile.TemporaryDirectory() as tempdir:
                backupfile = os.path.join(tempdir, 'nginx.backup.tar')
                backup_nginx_files(config, backupfile)
                try:
                    install_nginx_files(config, settings)
                    test_nginx_config()
                    reload_nginx_config()
                except Exception as e:
                    try:
                        print('Restoring Nginx configuration to previous state...')
                        restore_nginx_files(config, backupfile)
                        test_nginx_config()
                        reload_nginx_config()
                        print('Nginx previous configuration restored and loaded')
                    except Exception as e:
                        print('ERROR: Failed to restore Nginx config:', e, file=sys.stderr)
                        print('ERROR: Nginx config left corrupted!', file=sys.stderr)
                    raise
        elif service == 'nginxmain':
            targetfile = '/etc/nginx/nginx.conf'
            with tempfile.TemporaryDirectory() as tempdir:
                backupfile = os.path.join(tempdir, 'nginx.conf')
                shutil.copy(targetfile, backupfile)
                try:
                    srcfile = os.path.join(HERE, 'nginxmain', '{}.conf'.format(config))
                    shutil.copy(srcfile, targetfile)
                    test_nginx_config()
                    reload_nginx_config()
                except Exception as e:
                    try:
                        print('Restoring Nginx configuration to previous state...')
                        shutil.copy(backupfile, targetfile)
                        test_nginx_config()
                        reload_nginx_config()
                        print('Nginx previous configuration restored and loaded')
                    except Exception as e:
                        print('ERROR: Failed to restore Nginx config:', e, file=sys.stderr)
                        print('ERROR: Nginx config left corrupted!', file=sys.stderr)
                    raise
        else:
            raise Exception('Unsupported service: {}'.format(service))
    except Exception as e:
        print('ERROR: Failed to install service configuration:', e, file=sys.stderr)
        sys.exit(1)
    print('Service [{}] configuration [{}] installed'.format(service, config))


@cli.command()
@click.argument('service')
@click.argument('config')
def uninstall(service, config):
    """Uninstall service configuration"""
    print('Removing service [{}] for config [{}]...'.format(service, config))
    settings, error = load_settings(service, config)
    if error is not None:
        print('ERROR:', error, file=sys.stderr)
        sys.exit(1)
    try:
        if service == 'nginxsite':
            uninstall_nginx_files(config, settings)
            test_nginx_config()
            reload_nginx_config()
        elif service == 'nginxmain':
            print('Fake uninstall of nginxmain')
        else:
            raise Exception('Unsupported service: {}'.format(service))
    except Exception as e:
        print('ERROR: Failed to uninstall service configuration:', e, file=sys.stderr)
        sys.exit(1)
    print('Service [{}] configuration [{}] uninstalled'.format(service, config))


if __name__ == '__main__':
    cli()
