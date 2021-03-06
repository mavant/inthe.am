from contextlib import contextmanager
import datetime
import logging
import os
import uuid

from django.conf import settings
from django.utils.timezone import now, utc

from lockfile import LockTimeout
from lockfile.pidlockfile import PIDLockFile


logger = logging.getLogger(__name__)


@contextmanager
def git_checkpoint(
    store, message, function=None, args=None, kwargs=None,
    sync=False, gc=True, notify_rollback=True,
):
    lockfile_path = os.path.join(store.local_path, '.lock')
    pre_work_sha = store.repository.head()
    checkpoint_id = uuid.uuid4()
    try:
        with PIDLockFile(lockfile_path, timeout=10):
            store.create_git_repository()
            try:
                store.create_git_checkpoint(
                    message,
                    function=function,
                    args=args,
                    kwargs=kwargs,
                    pre_operation=True,
                    checkpoint_id=checkpoint_id,
                )
                yield
                # We need to force taskw to garbage collect after engaging
                # in operations that might alter the task ID#s, otherwise
                # they'll hang out as uncommitted changes until the next
                # writing operation.
                if gc:
                    store.client.filter_tasks({'status': 'pending'})
                store.create_git_checkpoint(
                    message,
                    function=function,
                    args=args,
                    kwargs=kwargs,
                    checkpoint_id=checkpoint_id,
                )
            except Exception as e:
                store.create_git_checkpoint(
                    str(e),
                    function=function,
                    args=args,
                    kwargs=kwargs,
                    rollback=True
                )
                dangling_sha = store.repository.head()
                changes_were_stored = (
                    dangling_sha and dangling_sha != pre_work_sha
                )
                if changes_were_stored:
                    logger.exception(
                        "An error occurred that required rolling-back "
                        "the git repository at %s from %s to %s.",
                        store.local_path,
                        dangling_sha,
                        pre_work_sha,
                    )
                    if notify_rollback:
                        store.log_error(
                            "An error occurred while interacting with your "
                            "task list, and your task list was recovered by "
                            "rolling-back to the last known good state (%s).  "
                            "Since your task list is synchronized with a "
                            "taskd server, this will likely not have any "
                            "negative effects.  Rollback ID: %s.",
                            pre_work_sha,
                            dangling_sha,
                        )
                    store.git_reset(pre_work_sha)
                else:
                    logger.exception(
                        "An error occured that did not require rolling-back "
                        "the git repository at %s (at %s)",
                        store.local_path,
                        pre_work_sha
                    )
                raise
    except LockTimeout:
        lockfile_created = datetime.datetime.fromtimestamp(
            os.path.getctime(lockfile_path)
        ).replace(tzinfo=utc)
        creation_minimum = (
            now() - datetime.timedelta(
                seconds=settings.LOCKFILE_TIMEOUT_SECONDS
            )
        )
        if lockfile_created < creation_minimum:
            store.log_error(
                "An expired lockfile was found and deleted. "
                "Although the request that caused the lockfile to be "
                "deleted did fail, subsequent requests will "
                "be successful."
            )
            os.unlink(lockfile_path)
        raise
    if sync:
        store.sync()
