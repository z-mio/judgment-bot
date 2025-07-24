from importlib.util import find_spec
from importlib import import_module
import platform
import subprocess
from contextlib import suppress

from log import logger


def setup_optimized_event_loop():
    """配置优化的事件循环，自动选择winloop或uvloop"""
    is_windows = platform.system() == "Windows"
    loop_module = "winloop" if is_windows else "uvloop"

    # 检查模块是否已安装
    if find_spec(loop_module) is not None:
        # 动态导入并安装事件循环
        with suppress(Exception):
            module = import_module(loop_module)
            module.install()
            logger.info(f"{loop_module} 已启用")
            return True

    # 模块未安装，尝试安装
    logger.warning(f"{loop_module} 未安装，尝试安装...")
    try:
        result = subprocess.run(
            ["uv", "pip", "install", loop_module],
            capture_output=True,
            text=True,
            check=True,
        )

        if result.returncode == 0:
            # 安装成功，重新尝试加载模块
            logger.info(f"{loop_module} 安装成功")
            module = import_module(loop_module)
            module.install()
            logger.info(f"{loop_module} 已启用")
            return True
        else:
            logger.error(f"无法安装 {loop_module}: {result.stderr}")
    except Exception as e:
        logger.error(f"安装 {loop_module} 时出错: {str(e)}")

    logger.info("将使用标准 asyncio 事件循环")
    return False
