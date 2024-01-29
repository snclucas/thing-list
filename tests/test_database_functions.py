import unittest
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import SQLAlchemyError

# Assuming the database_functions file is inside project directory
from database_functions import get_user_template_by_id


class TestDatabaseFunctions(unittest.TestCase):

    @patch('database_functions.db')
    @patch('database_functions.FieldTemplate')
    @patch('database_functions.User')
    @patch('database_functions.select')
    @patch('database_functions.app')
    def test_get_user_template_by_id(self, mock_app, mock_select, mock_user, mock_field_template, mock_db):
        # Arrange
        session_mock = MagicMock()
        mock_db.session = session_mock
        query_mock = MagicMock()
        session_mock.execute.return_value = query_mock
        query_mock.one_or_none.return_value = 'template'
        mock_template_id = 1
        mock_user_id = 1

        # Act
        result = get_user_template_by_id(mock_template_id, mock_user_id)

        # Assert
        session_mock.execute.assert_called_once()
        query_mock.one_or_none.assert_called_once()
        self.assertEqual(result, 'template')

    @patch('database_functions.db')
    @patch('database_functions.FieldTemplate')
    @patch('database_functions.User')
    @patch('database_functions.select')
    @patch('database_functions.app')
    def test_get_user_template_by_id_returns_none_when_template_not_found(self, mock_app, mock_select, mock_user,
                                                                          mock_field_template, mock_db):
        # Arrange
        session_mock = MagicMock()
        mock_db.session = session_mock
        query_mock = MagicMock()
        session_mock.execute.return_value = query_mock
        query_mock.one_or_none.return_value = None
        mock_template_id = 1
        mock_user_id = 1

        # Act
        result = get_user_template_by_id(mock_template_id, mock_user_id)

        # Assert
        session_mock.execute.assert_called_once()
        self.assertEqual(result, None)

    @patch('project.database_functions.db')
    @patch('project.database_functions.FieldTemplate')
    @patch('project.database_functions.User')
    @patch('project.database_functions.select')
    @patch('project.database_functions.app')
    def test_get_user_template_by_id_handles_sqlalchemy_error(self, mock_app, mock_select, mock_user,
                                                              mock_field_template, mock_db):
        # Arrange
        session_mock = MagicMock()
        mock_db.session = session_mock
        session_mock.execute.side_effect = SQLAlchemyError()
        mock_template_id = 1
        mock_user_id = 1

        # Act
        result = get_user_template_by_id(mock_template_id, mock_user_id)

        # Assert
        session_mock.execute.assert_called_once()
        mock_app.logger.error.assert_called_once()
        self.assertEqual(result, None)


if __name__ == "__main__":
    unittest.main()
